import React, { useEffect, useId, useState } from "react";
import { getClinicDate } from "./appointmentFilters.js";
import "./BookingCalendar.css";

function monthDate(year, month, day = 1) {
    const value = new Date(0);
    value.setUTCFullYear(year, month - 1, day);
    return value;
}

export default function BookingCalendar({
    selectedDate,
    onSelectDate,
    disabled = false,
    label = "Ημερομηνία ραντεβού",
}) {
    const titleId = useId();
    const today = getClinicDate();
    const [visibleMonth, setVisibleMonth] = useState(() =>
        (selectedDate || today).slice(0, 7)
    );

    useEffect(() => {
        if (selectedDate) setVisibleMonth(selectedDate.slice(0, 7));
    }, [selectedDate]);

    const [year, month] = visibleMonth.split("-").map(Number);
    const firstDay = monthDate(year, month);
    const daysInMonth = monthDate(year, month + 1, 0).getUTCDate();
    const firstDayOffset = (firstDay.getUTCDay() + 6) % 7;
    const monthTitle = firstDay.toLocaleDateString("el-GR", {
        month: "long", year: "numeric", timeZone: "UTC",
    });

    function changeMonth(offset) {
        const next = monthDate(year, month + offset);
        if (next.getUTCFullYear() < 1 || next.getUTCFullYear() > 9998) return;
        setVisibleMonth(next.toISOString().slice(0, 7));
    }

    return (
        <div className="calendar-container booking-calendar" role="group" aria-label={label}>
            <div className="calendar-header">
                <button type="button" aria-label="Προηγούμενος μήνας"
                    disabled={disabled || (year === 1 && month === 1)}
                    onClick={() => changeMonth(-1)}>&lt;</button>
                <span id={titleId} className="booking-calendar-title" aria-live="polite">{monthTitle}</span>
                <button type="button" aria-label="Επόμενος μήνας"
                    disabled={disabled || (year === 9998 && month === 12)}
                    onClick={() => changeMonth(1)}>&gt;</button>
            </div>
            <div className="calendar-grid" aria-labelledby={titleId}>
                {["Δε", "Τρ", "Τε", "Πε", "Πα", "Σα", "Κυ"].map(day => <span key={day}>{day}</span>)}
                {Array.from({ length: firstDayOffset }, (_, index) => <span key={`empty-${index}`} aria-hidden="true" />)}
                {Array.from({ length: daysInMonth }, (_, index) => {
                    const day = index + 1;
                    const date = `${visibleMonth}-${String(day).padStart(2, "0")}`;
                    const weekday = monthDate(year, month, day).getUTCDay();
                    const unavailable = disabled || weekday === 0 || weekday === 6 || date < today;
                    const selected = selectedDate === date;
                    return (
                        <button key={date} type="button" data-date={date}
                            className={`calendar-day ${unavailable ? "disabled" : selected ? "selected" : "available"}`}
                            disabled={unavailable} aria-pressed={selected}
                            aria-label={`${day} ${monthTitle}`}
                            onClick={() => onSelectDate(date)}>{day}</button>
                    );
                })}
            </div>
            {selectedDate && <p className="booking-calendar-selection">
                Επιλεγμένη ημέρα: {new Date(`${selectedDate}T12:00:00Z`).toLocaleDateString("el-GR", {
                    day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC",
                })}
            </p>}
        </div>
    );
}
