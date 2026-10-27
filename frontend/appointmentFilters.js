const clinicDateFormatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Athens", year: "numeric", month: "2-digit", day: "2-digit",
});

export function matchesAppointmentFilters(appointment, amka = "", date = "") {
    if (amka && appointment.patient_AMKA !== amka) return false;
    if (!date) return true;
    const parts = clinicDateFormatter.formatToParts(new Date(appointment.starts_at));
    const part = (type) => parts.find((item) => item.type === type).value;
    return `${part("year")}-${part("month")}-${part("day")}` === date;
}

export function getClinicDate(value = new Date()) {
    const parts = clinicDateFormatter.formatToParts(value);
    const part = (type) =>
        parts.find((item) => item.type === type).value;

    return `${part("year")}-${part("month")}-${part("day")}`;
}

export function clinicSlotToIso(day, slot) {
    if (
        !/^\d{4}-\d{2}-\d{2}$/.test(day) ||
        !/^(09|1[0-6]):(00|30)$/.test(slot)
    ) {
        throw new Error("Μη έγκυρη ημερομηνία ή ώρα.");
    }

    const reference = new Date(`${day}T12:00:00Z`);

    if (
        Number.isNaN(reference.getTime()) ||
        reference.toISOString().slice(0, 10) !== day
    ) {
        throw new Error("Μη έγκυρη ημερομηνία.");
    }

    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: "Europe/Athens",
        timeZoneName: "longOffset",
    }).formatToParts(reference);

    const zoneName = parts.find(
        (part) => part.type === "timeZoneName"
    )?.value;

    const offset = zoneName?.replace(/^GMT/, "");

    if (!/^\+\d{2}:\d{2}$/.test(offset || "")) {
        throw new Error("Δεν προσδιορίστηκε η ώρα Ελλάδας.");
    }

    return `${day}T${slot}:00${offset}`;
}
