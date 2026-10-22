from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
    StrictBool,
)

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from auth import require_staff_change
from database import (
    create_availability_block,
    release_availability_block,
    get_availability_blocks,
)

from auth import require_staff


class AvailabilityBlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=200,
        ),
    ]

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError(
                "Το τέλος του αποκλεισμού πρέπει να είναι "
                "μετά την αρχή."
            )

        return self


class AvailabilityBlockLocalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_date: date
    all_day: StrictBool = False
    start_time: time | None = None
    end_time: time | None = None
    reason: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=200,
        ),
    ]

    def to_interval(self):
        athens = ZoneInfo("Europe/Athens")

        if self.all_day:
            start = datetime.combine(
                self.local_date,
                time.min,
                tzinfo=athens,
            )
            end = datetime.combine(
                self.local_date + timedelta(days=1),
                time.min,
                tzinfo=athens,
            )
            return start, end

        if self.start_time is None or self.end_time is None:
            raise ValueError("Συμπλήρωσε ώρα έναρξης και λήξης.")

        values = []

        for selected_time in (self.start_time, self.end_time):
            if selected_time.tzinfo is not None:
                raise ValueError(
                    "Οι ώρες πρέπει να δίνονται ως τοπικές ώρες Ελλάδας."
                )

            naive = datetime.combine(self.local_date, selected_time)
            aware = naive.replace(tzinfo=athens)

            round_trip = aware.astimezone(
                timezone.utc
            ).astimezone(athens).replace(tzinfo=None)

            if round_trip != naive:
                raise ValueError(
                    "Η ώρα δεν υπάρχει λόγω αλλαγής θερινής ώρας."
                )

            if aware.utcoffset() != aware.replace(fold=1).utcoffset():
                raise ValueError(
                    "Η ώρα είναι διφορούμενη λόγω αλλαγής θερινής ώρας."
                )

            values.append(aware)

        return values[0], values[1]

    @model_validator(mode="after")
    def validate_local_interval(self) -> Self:
        start, end = self.to_interval()

        if end <= start:
            raise ValueError(
                "Η ώρα λήξης πρέπει να είναι μετά την ώρα έναρξης."
            )

        return self

router = APIRouter(prefix="/availability-blocks")


@router.post("", status_code=201)
def create_block(
    block: AvailabilityBlockCreate,
    response: Response,
    session: dict = Depends(require_staff_change),
):
    if block.starts_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Ο αποκλεισμός πρέπει να ξεκινά στο μέλλον.",
        )

    created = create_availability_block(
        block.starts_at,
        block.ends_at,
        block.reason,
        session["issuer"],
        session["subject"],
        uuid4(),
    )

    if created is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Το διάστημα επικαλύπτει ενεργό ραντεβού "
                "ή άλλον αποκλεισμό."
            ),
            headers={"Cache-Control": "no-store"},
        )

    response.headers["Cache-Control"] = "no-store"
    return created


@router.post("/{block_id}/release")
def release_block(
    block_id: int,
    response: Response,
    session: dict = Depends(require_staff_change),
):
    released = release_availability_block(
        block_id,
        session["issuer"],
        session["subject"],
        uuid4(),
    )

    if released is None:
        raise HTTPException(
            status_code=404,
            detail="Δεν βρέθηκε ενεργός αποκλεισμός.",
            headers={"Cache-Control": "no-store"},
        )

    response.headers["Cache-Control"] = "no-store"
    return released

@router.get("")
def list_blocks(
    response: Response,
    session: dict = Depends(require_staff),
):
    response.headers["Cache-Control"] = "no-store"
    return get_availability_blocks()

@router.post("/local", status_code=201)
def create_local_block(
    block: AvailabilityBlockLocalCreate,
    response: Response,
    session: dict = Depends(require_staff_change),
):
    starts_at, ends_at = block.to_interval()

    return create_block(
        block=AvailabilityBlockCreate(
            starts_at=starts_at,
            ends_at=ends_at,
            reason=block.reason,
        ),
        response=response,
        session=session,
    )