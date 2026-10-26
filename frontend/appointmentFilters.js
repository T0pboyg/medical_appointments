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
