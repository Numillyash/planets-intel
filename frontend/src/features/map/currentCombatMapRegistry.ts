const currentCombatPositions = new Set<string>();
let registeredTurn: number | null = null;

function positionKey(x: number, y: number): string {
    return `${x}:${y}`;
}

export function resetCurrentCombatPositions(turn: number): void {
    registeredTurn = turn;
    currentCombatPositions.clear();
}

export function registerCurrentCombatPosition(
    turn: number,
    x: number | null,
    y: number | null,
): void {
    if (registeredTurn !== turn) resetCurrentCombatPositions(turn);
    if (x === null || y === null) return;
    currentCombatPositions.add(positionKey(x, y));
}

export function hasCurrentCombatPosition(
    turn: number,
    x: number,
    y: number,
): boolean {
    return registeredTurn === turn && currentCombatPositions.has(positionKey(x, y));
}
