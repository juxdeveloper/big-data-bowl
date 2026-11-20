export type Slot = {
  slot: string
  nflId: number
  x: number
  y: number
  snaps: number
  slotShare: number
  role: string
  unit?: 'OFF' | 'DEF'
  name: string
  jersey: number | null
  position: string
  team: string
}

export type Alternative = {
  config: string
  n: number
  asv: number
  successRate: number
  expected: number
  leagueAsv: number | null
}

export type TeamProfile = {
  team: string
  profile: string
  available: string[]
  config: string
  n: number
  asv: number
  successRate: number
  expected: number
  leagueAsv: number | null
  alternatives: Alternative[]
  lineup: Slot[]
  inactive: {
    nflId: number
    name: string
    jersey: number | null
    position: string
    plays: number
    team: string
  }[]
}

export type Player = {
  nflId: number
  name: string
  position: string
  team: string
  jersey: number | null
  height: string
  heightIn: number | null
  weight: number
  age: number | null
  college: string | null
  plays: number
  rushSnaps: number
  blockSnaps: number
  coverageSnaps: number
  routeSnaps: number
  passSnaps: number
  pressures: number
  hits: number
  sacks: number
  pressuresAllowed: number
  hitsAllowed: number
  sacksAllowed: number
  beaten: number
  penalties: number
  penaltyKinds: Record<string, number>
  asvOnField: number
  topSpeed: number | null
  topAccel: number | null
  pressureRate: number | null
  pressureAllowedRate: number | null
  attempts?: number
  completions?: number
  completionPct?: number | null
  interceptions?: number
  sacksTaken?: number
  scrambles?: number
  netYards?: number
  yardsPerAttempt?: number | null
  passTD?: number
  peerGroup?: { position: string; n: number }
  percentiles?: Record<string, number | null>
}

export type Meta = {
  ready: boolean
  metric: {
    name: string
    longName: string
    definition: string
    successDefinition: string
    expectation: string
    units: string
    shrinkage: string
    limitations: string[]
  }
  model: Record<string, number>
  scope: Record<string, number | number[]>
  teams: string[]
  topOffenseConfigs: { config: string; n: number; asv: number }[]
  topDefenseConfigs: { config: string; n: number; asv: number }[]
  teamRankOffense: { team: string; asv: number }[]
  teamRankDefense: { team: string; asv: number }[]
  coefficients: Record<string, number>
  challenger: {
    arch: string
    device: string
    features: number
    auc_test: number
    logloss_test: number
    params: number
  } | null
  deep: {
    arch: string
    device: string
    params: number
    auc_cv: number
    logloss_cv: number
    logloss_baseline: number
    folds: number[]
    validation: string
    augmentation: string
    trackingRowsUsed: number
    shape: { players: number; frames: number; channels: number; situational: number }
    channels: string[]
    trainSeconds: number
  } | null
  ai: { enabled: boolean; quota: number; remaining: number }
}

/** Ruta estática equivalente, para la demo pública servida sin backend. */
function staticPath(path: string): string {
  if (path.startsWith('api/meta')) return 'static/meta.json'
  if (path.startsWith('api/team/')) {
    const [, rest] = path.split('api/team/')
    const [abbr, query] = rest.split('?')
    const profile = new URLSearchParams(query ?? '').get('profile') ?? 'GENERAL'
    return `static/team-${abbr}-${profile}.json`
  }
  if (path.startsWith('api/player/')) return `static/player-${path.split('api/player/')[1]}.json`
  if (path.startsWith('api/players')) return 'static/players.json'
  return path
}

export async function get<T>(path: string): Promise<T> {
  try {
    const r = await fetch(path)
    if (r.ok) return (await r.json()) as T
  } catch {
    /* sin backend: se intenta la copia estática */
  }
  const s = await fetch(staticPath(path))
  if (!s.ok) throw new Error(String(s.status))
  return (await s.json()) as T
}

// Identidad de equipo. El color solo codifica dato, nunca decora.
export const TEAM_COLOR: Record<string, string> = {
  ARI: '#97233F', ATL: '#A71930', BAL: '#241773', BUF: '#00338D', CAR: '#0085CA',
  CHI: '#0B162A', CIN: '#FB4F14', CLE: '#311D00', DAL: '#041E42', DEN: '#FB4F14',
  DET: '#0076B6', GB: '#203731', HOU: '#03202F', IND: '#002C5F', JAX: '#006778',
  KC: '#E31837', LA: '#003594', LAC: '#0080C6', LV: '#101418', MIA: '#008E97',
  MIN: '#4F2683', NE: '#002244', NO: '#9F8958', NYG: '#0B2265', NYJ: '#125740',
  PHI: '#004C54', PIT: '#101820', SEA: '#002244', SF: '#AA0000', TB: '#D50A0A',
  TEN: '#0C2340', WAS: '#5A1414',
}

export const teamColor = (t?: string): string => (t && TEAM_COLOR[t]) || '#14161a'

export const pct = (v: number | null | undefined, d = 1): string =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(d)}%`

export const asv100 = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}`

export const num = (v: number | null | undefined, d = 0): string =>
  v === null || v === undefined ? '—' : v.toFixed(d)

export const PROFILE_LABEL: Record<string, string> = {
  GENERAL: 'General',
  ATAQUE: 'Ofensivo',
  DEFENSA: 'Defensivo',
}

export const PROFILE_BLURB: Record<string, string> = {
  GENERAL: 'Las 22 titularidades: el mejor acomodo ofensivo y el mejor defensivo del equipo en la temporada.',
  ATAQUE: 'El acomodo con el que el equipo gana más jugadas de lo esperado cuando tiene el balón.',
  DEFENSA: 'El acomodo con el que el equipo niega más jugadas de lo esperado cuando defiende.',
}
