export function latestDeviceActivity(...timestamps: (Date | string | null | undefined)[]): Date | null {
    let latest: Date | null = null;
    for (const timestamp of timestamps) {
        if (timestamp == null) continue;
        const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
        if (Number.isFinite(date.getTime()) && (!latest || date.getTime() > latest.getTime())) latest = date;
    }
    return latest;
}
