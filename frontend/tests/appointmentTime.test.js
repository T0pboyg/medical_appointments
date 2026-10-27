import test from "node:test";
import assert from "node:assert/strict";
import { clinicSlotToIso } from "../appointmentFilters.js";

test("winter appointment uses Athens UTC+02", () => {
    assert.equal(
        clinicSlotToIso("2030-01-07", "10:30"),
        "2030-01-07T10:30:00+02:00"
    );
});

test("summer appointment uses Athens UTC+03", () => {
    assert.equal(
        clinicSlotToIso("2030-07-08", "10:30"),
        "2030-07-08T10:30:00+03:00"
    );
});

test("invalid dates and slots are rejected", () => {
    for (const [day, slot] of [
        ["2030-02-30", "10:30"],
        ["2030-01-07", "10:15"],
        ["2030-01-07", "17:00"],
        ["not-a-date", "10:30"],
    ]) {
        assert.throws(() => clinicSlotToIso(day, slot));
    }
});