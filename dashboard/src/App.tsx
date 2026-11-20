import { Component, useEffect, useMemo, useState } from 'react'
import { IconBack, IconGroups, IconMoon, IconSearch, IconShield, IconSun, IconTarget } from './icons'
import { Bar, FieldMap, Helmet, LineupTable, PlayerAvatar, Rusher, Stat } from './components'
import type { Meta, Player, TeamProfile } from './lib'
import { PROFILE_BLURB, PROFILE_LABEL, asv100, get, num, pct, teamColor } from './lib'

const PROFILES = ['GENERAL', 'ATAQUE', 'DEFENSA'] as const

function useRoute(): string {
  const [h, setH] = useState(window.location.hash)
  useEffect(() => {
    const f = () => setH(window.location.hash)
    window.addEventListener('hashchange', f)
    return () => window.removeEventListener('hashchange', f)
  }, [])
  return h
}

/** Ningún fallo de render debe dejar la página en blanco: se aísla y se reporta. */
class Boundary extends Component<{ children: React.ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-xl px-5 py-20">
          <div className="eyebrow">Error en la vista</div>
          <p className="mt-2 text-[13px] text-ink2">
            Algo falló al dibujar esta sección. El resto del análisis sigue disponible.
          </p>
          <pre className="mt-3 overflow-x-auto border rule bg-white p-3 text-[11px] text-dim">
            {String(this.state.error?.message ?? this.state.error)}
          </pre>
          <button
            type="button"
            onClick={() => {
              window.location.hash = '#/'
              this.setState({ error: null })
            }}
            className="mt-4 border border-invert bg-invert px-3 py-1.5 text-[12px] text-white"
          >
            Volver al acomodo
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

const goPlayer = (id: number) => {
  window.location.hash = `#/jugador/${id}`
}
const goHome = () => {
  window.location.hash = '#/'
}

export default function App() {
  const route = useRoute()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [err, setErr] = useState(false)

  useEffect(() => {
    get<Meta>('api/meta').then(setMeta).catch(() => setErr(true))
  }, [])

  const playerId = useMemo(() => {
    const m = route.match(/#\/jugador\/(\d+)/)
    return m ? Number(m[1]) : null
  }, [route])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [playerId])

  if (err)
    return (
      <Shell>
        <p className="py-20 text-center text-sm text-dim">
          No se pudieron cargar los datos del análisis.
        </p>
      </Shell>
    )
  if (!meta)
    return (
      <Shell>
        <p className="py-20 text-center text-sm text-dim">Cargando modelo…</p>
      </Shell>
    )

  return (
    <Shell meta={meta}>
      <Boundary>{playerId ? <PlayerPage id={playerId} /> : <TeamPage meta={meta} />}</Boundary>
      <Rusher enabled={meta.ai.enabled} quota={meta.ai.quota} />
    </Shell>
  )
}

/* ------------------------------------------------------------------ marco */
function useTheme(): [string, () => void] {
  const [theme, setTheme] = useState<string>(() => localStorage.getItem('asv-theme') ?? 'dark')
  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem('asv-theme', theme)
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

function Shell({ children, meta }: { children: React.ReactNode; meta?: Meta }) {
  const [theme, toggle] = useTheme()
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 border-b rule bg-app-blur">
        <div className="mx-auto flex max-w-[1240px] items-center justify-between gap-4 px-5 py-3">
          <button onClick={goHome} className="focusable flex items-center gap-3 text-left" aria-label="Inicio">
            <IconShield size={28} className="text-accent" />
            <span>
              <span className="display block text-[20px] leading-none">ASV</span>
              <span className="label mt-0.5 block text-[10px]">Alignment Success Value</span>
            </span>
          </button>
          <div className="flex items-center gap-5">
            <div className="hidden text-right sm:block">
              <div className="label text-[10px]">
                Data Rushers · Big Data Bowl 2026 · Entrenador
              </div>
              {meta ? (
                <div className="num mt-0.5 text-[11px] text-faint">
                  {String(meta.scope.analyzedPlays)} jugadas · {String(meta.scope.games)} partidos · 2021 S1–8
                </div>
              ) : null}
            </div>
            <button
              onClick={toggle}
              className="focusable flex h-10 w-10 items-center justify-center border rule text-dim transition-colors hover:text-ink"
              aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
              title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
            >
              {theme === 'dark' ? <IconSun size={22} /> : <IconMoon size={22} />}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1240px] px-5 pb-28 pt-8">{children}</main>
      <footer className="border-t rule">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-2 px-5 py-5 text-[11px] text-faint">
          <span className="label text-[10px]">Data Rushers · UNAM · AWS · NFL</span>
          <span>NFL Next Gen Stats y Pro Football Focus, temporada 2021</span>
        </div>
      </footer>
    </div>
  )
}

/* ------------------------------------------------------------- vista equipo */
function TeamPage({ meta }: { meta: Meta }) {
  const [team, setTeam] = useState(meta.teamRankOffense[0]?.team ?? 'TB')
  const [profile, setProfile] = useState<string>('GENERAL')
  const [data, setData] = useState<TeamProfile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    get<TeamProfile>(`api/team/${team}?profile=${profile}`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [team, profile])

  const vsLeague = data && data.leagueAsv !== null ? data.asv - data.leagueAsv : null

  return (
    <div className="space-y-8">
      {/* titular */}
      <section>
        <div className="eyebrow">La decisión</div>
        <h1 className="mt-1 max-w-4xl text-[26px] font-semibold leading-[1.15] tracking-tight sm:text-[32px]">
          {data ? (
            <>
              {team} gana{' '}
              <span className="num" style={{ color: teamColor(team) }}>
                {asv100(data.asv)}
              </span>{' '}
              jugadas exitosas por cada 100 snaps cuando se acomoda en{' '}
              <span className="underline decoration-[color:var(--accent)] decoration-2 underline-offset-4">{data.config}</span>.
            </>
          ) : (
            'Cargando acomodo…'
          )}
        </h1>
        <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-ink2">
          {PROFILE_BLURB[profile]} ASV compara el resultado real contra el que el modelo esperaba dada la situación
          de juego, así que no premia a quien enfrentó terceras y corta.
        </p>
      </section>

      {/* controles */}
      <section className="flex flex-wrap items-center justify-between gap-4 border-y rule py-3">
        <div className="flex flex-wrap items-center gap-2">
          {PROFILES.map((p) => {
            const Icon = p === 'GENERAL' ? IconGroups : p === 'ATAQUE' ? IconTarget : IconShield
            return (
              <button
                key={p}
                onClick={() => setProfile(p)}
                className={`focusable flex items-center gap-2 border px-4 py-2 text-[13px] font-semibold uppercase tracking-wider transition-colors ${
                  profile === p ? 'tab-active' : 'rule text-dim hover:text-ink'
                }`}
              >
                <Icon size={20} />
                {PROFILE_LABEL[p]}
              </button>
            )
          })}
        </div>
        <label className="flex items-center gap-2 text-[12px] text-dim">
          <IconSearch size={20} />
          <select
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="num focusable border rule bg-surface px-3 py-2 text-[14px] font-semibold text-ink outline-none"
            aria-label="Equipo"
          >
            {meta.teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </section>

      {/* mapa + metricas */}
      <section className="grid gap-8 lg:grid-cols-[1.55fr_1fr]">
        <div>
          <h3 className="eyebrow mb-2">Mapa del acomodo óptimo · {PROFILE_LABEL[profile]}</h3>
          {data ? <FieldMap lineup={data.lineup} team={team} onOpen={goPlayer} /> : <div className="h-80 bg-raised" />}
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 self-start">
          <Stat label="ASV del acomodo" value={data ? asv100(data.asv) : '—'} sub="jugadas exitosas por 100 snaps sobre lo esperado" accent />
          <Stat label="Snaps observados" value={data ? num(data.n) : '—'} sub="tamaño de muestra tras filtrar" />
          <Stat label="Éxito observado" value={data ? pct(data.successRate) : '—'} sub="definición estándar de jugada exitosa" />
          <Stat label="Éxito esperado" value={data ? pct(data.expected) : '—'} sub="salida del modelo situacional" />
          <Stat label="Contra la liga" value={vsLeague === null ? '—' : asv100(vsLeague)} sub="ASV del equipo menos ASV liga en el mismo acomodo" />
          <Stat label="AUC del modelo" value={num(meta.model.auc_test, 3)} sub={`validación por partido, n=${meta.model.n_test}`} />
          {loading ? <div className="col-span-2 text-[11px] text-dim">Actualizando…</div> : null}
        </div>
      </section>

      {/* alternativas */}
      {data && data.alternatives.length ? (
        <section>
          <h3 className="eyebrow mb-1">Por qué este acomodo y no otro</h3>
          <p className="mb-3 max-w-2xl text-[12px] text-dim">
            Todos los acomodos de {team} con muestra suficiente, ordenados por ASV contraído.
          </p>
          <table className="w-full border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-y rule text-[10px] uppercase tracking-[0.1em] text-dim">
                <th className="py-2 font-medium">Acomodo</th>
                <th className="py-2 text-right font-medium">Snaps</th>
                <th className="py-2 text-right font-medium">Éxito</th>
                <th className="hidden py-2 text-right font-medium sm:table-cell">Esperado</th>
                <th className="py-2 text-right font-medium">ASV</th>
                <th className="hidden py-2 text-right font-medium md:table-cell">ASV liga</th>
              </tr>
            </thead>
            <tbody>
              {data.alternatives.map((a, i) => (
                <tr key={a.config} className={`border-b rule ${i === 0 ? 'bg-highlight' : ''}`}>
                  <td className="py-2 font-medium">{a.config}</td>
                  <td className="num py-2 text-right">{a.n}</td>
                  <td className="num py-2 text-right">{pct(a.successRate)}</td>
                  <td className="num hidden py-2 text-right text-dim sm:table-cell">{pct(a.expected)}</td>
                  <td className="num py-2 text-right font-semibold">{asv100(a.asv)}</td>
                  <td className="num hidden py-2 text-right text-dim md:table-cell">{asv100(a.leagueAsv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {/* roster */}
      {data ? (
        <section>
          <h3 className="eyebrow mb-3">Alineación y rotación</h3>
          <LineupTable data={data} onOpen={goPlayer} />
        </section>
      ) : null}

      {/* metodologia */}
      <section className="grid gap-8 border-t rule pt-6 md:grid-cols-3">
        <div>
          <h3 className="eyebrow mb-2">Cómo se calcula</h3>
          <p className="text-[12px] leading-relaxed text-ink2">{meta.metric.definition}</p>
          <p className="mt-2 text-[12px] leading-relaxed text-ink2">{meta.metric.successDefinition}</p>
          <p className="mt-2 text-[12px] leading-relaxed text-ink2">{meta.metric.expectation}</p>
          <dl className="mt-3 space-y-1 text-[11px] text-dim">
            <div className="flex justify-between border-t rule pt-1">
              <dt>Unidades</dt>
              <dd className="num text-right">{meta.metric.units}</dd>
            </div>
            <div className="flex justify-between border-t rule pt-1">
              <dt>Contracción</dt>
              <dd className="num">{meta.metric.shrinkage}</dd>
            </div>
            <div className="flex justify-between border-t rule pt-1">
              <dt>Log-loss modelo / base</dt>
              <dd className="num">
                {num(meta.model.logloss_test, 3)} / {num(meta.model.logloss_baseline, 3)}
              </dd>
            </div>
          </dl>
          {meta.challenger || meta.deep ? (
            <div className="mt-3 border-t rule pt-2">
              <div className="eyebrow mb-1.5">Modelos evaluados</div>
              <table className="w-full border-collapse text-[11px]">
                <thead>
                  <tr className="text-[9px] uppercase tracking-[0.1em] text-faint">
                    <th className="py-1 text-left font-medium">Modelo</th>
                    <th className="py-1 text-right font-medium">Parám.</th>
                    <th className="py-1 text-right font-medium">AUC</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t rule bg-highlight">
                    <td className="py-1.5">Logística situacional (producción)</td>
                    <td className="num py-1.5 text-right">17</td>
                    <td className="num py-1.5 text-right font-semibold">{num(meta.model.auc_test, 4)}</td>
                  </tr>
                  {meta.challenger ? (
                    <tr className="border-t rule">
                      <td className="py-1.5 text-ink2">MLP situacional (A100)</td>
                      <td className="num py-1.5 text-right text-dim">9,185</td>
                      <td className="num py-1.5 text-right">{num(meta.challenger.auc_test, 4)}</td>
                    </tr>
                  ) : null}
                  {meta.deep ? (
                    <tr className="border-t rule">
                      <td className="py-1.5 text-ink2">Trayectorias completas (A100)</td>
                      <td className="num py-1.5 text-right text-dim">
                        {meta.deep.params.toLocaleString('es-MX')}
                      </td>
                      <td className="num py-1.5 text-right">{num(meta.deep.auc_cv, 4)}</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
              {meta.deep ? (
                <p className="mt-2 text-[11px] leading-relaxed text-dim">
                  El modelo de trayectorias consume{' '}
                  <span className="num">{meta.deep.trackingRowsUsed.toLocaleString('es-MX')}</span> observaciones de
                  tracking ({meta.deep.shape.players} jugadores × {meta.deep.shape.frames} frames ×{' '}
                  {meta.deep.shape.channels} canales por jugada), con agregación de conjunto por unidad y espejo
                  lateral del campo como aumento. Validación en {meta.deep.validation}: AUC{' '}
                  <span className="num">{num(meta.deep.auc_cv, 4)}</span> contra{' '}
                  <span className="num">{num(meta.model.auc_test, 4)}</span> de la logística. La ganancia es de{' '}
                  <span className="num">{((meta.deep.auc_cv - meta.model.auc_test) * 1000).toFixed(1)}</span>{' '}
                  milésimas de AUC con 4,000 veces más parámetros: medimos el trayecto completo y confirmamos que el
                  acomodo pre-snap ya contiene casi toda la señal. Producción se queda con el modelo chico y
                  auditable.
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
        <div>
          <h3 className="eyebrow mb-2">Mejores acomodos de la liga</h3>
          <ul className="text-[12px]">
            {meta.topOffenseConfigs.slice(0, 6).map((c) => (
              <li key={c.config} className="flex justify-between gap-3 border-t rule py-1.5">
                <span className="text-ink2">{c.config}</span>
                <span className="num shrink-0 font-medium">{asv100(c.asv)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="eyebrow mb-2">Límites de los datos</h3>
          <ul className="space-y-1.5 text-[11px] leading-relaxed text-dim">
            {meta.metric.limitations.map((l) => (
              <li key={l} className="border-t rule pt-1.5">
                {l}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  )
}

/* ----------------------------------------------------------- vista jugador */
function PlayerPage({ id }: { id: number }) {
  const [p, setP] = useState<Player | null>(null)
  const [err, setErr] = useState(false)

  useEffect(() => {
    setP(null)
    setErr(false)
    get<Player>(`api/player/${id}`).then(setP).catch(() => setErr(true))
  }, [id])

  if (err) return <p className="py-20 text-center text-sm text-dim">Jugador no encontrado.</p>
  if (!p) return <p className="py-20 text-center text-sm text-dim">Cargando perfil…</p>

  const isQB = (p.attempts ?? 0) > 0
  const isRusher = p.rushSnaps >= 10
  const isBlocker = p.blockSnaps >= 10
  const pr = p.percentiles ?? {}

  return (
    <div className="space-y-8 fade-in">
      <button onClick={goHome} className="focusable flex items-center gap-2 label hover:text-ink">
        <IconBack size={20} /> Volver al acomodo
      </button>

      {/* tarjeta */}
      <section className="grid gap-6 border-b rule pb-7 sm:grid-cols-[auto_1fr]">
        <PlayerAvatar p={p} />
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <Helmet team={p.team} jersey={p.jersey} size={30} />
            <span className="eyebrow">
              {p.team} · {p.position}
            </span>
          </div>
          <h1 className="mt-2 text-[30px] font-semibold leading-none tracking-tight sm:text-[40px]">{p.name}</h1>
          <dl className="mt-5 grid max-w-2xl grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
            {[
              ['Edad', p.age === null ? 'n/d' : `${p.age} años`],
              ['Peso', `${p.weight} lb`],
              ['Altura', `${p.height} (${p.heightIn ?? '—'}")`],
              ['Dorsal', p.jersey === null ? 'n/d' : `#${p.jersey}`],
              ['Universidad', p.college ?? 'n/d'],
              ['Posición oficial', p.position],
              ['Snaps de pase', num(p.plays)],
              ['ASV con él en campo', asv100(p.asvOnField)],
            ].map(([k, v]) => (
              <div key={k as string} className="border-t rule pt-1.5">
                <dt className="eyebrow">{k}</dt>
                <dd className="num mt-0.5 truncate text-[13px] font-medium" title={String(v)}>
                  {v}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* estadisticas */}
      <section>
        <h3 className="eyebrow mb-3">Rendimiento en las semanas 1–8</h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 lg:grid-cols-4">
          {isQB ? (
            <>
              <Stat label="Pases completos" value={`${p.completions} / ${p.attempts}`} sub={`precisión ${pct(p.completionPct)}`} />
              <Stat label="Yardas netas" value={num(p.netYards)} sub={`${num(p.yardsPerAttempt, 2)} por intento`} />
              <Stat label="Anotaciones" value={num(p.passTD)} sub="derivadas del play-by-play" />
              <Stat label="Intercepciones" value={num(p.interceptions)} sub={`${p.sacksTaken} capturas recibidas`} />
            </>
          ) : null}
          {isRusher ? (
            <>
              <Stat label="Presiones generadas" value={num(p.pressures + p.hits + p.sacks)} sub={`${p.sacks} capturas · ${p.hits} golpes`} />
              <Stat label="Tasa de presión" value={pct(p.pressureRate)} sub={`en ${p.rushSnaps} snaps de rush`} />
            </>
          ) : null}
          {isBlocker ? (
            <>
              <Stat label="Presiones permitidas" value={num(p.pressuresAllowed + p.hitsAllowed + p.sacksAllowed)} sub={`${p.sacksAllowed} capturas permitidas`} />
              <Stat label="Tasa permitida" value={pct(p.pressureAllowedRate)} sub={`en ${p.blockSnaps} snaps de protección`} />
              <Stat label="Superado por el rusher" value={num(p.beaten)} sub="sin derivar en presión" />
            </>
          ) : null}
          {p.coverageSnaps >= 10 ? (
            <Stat label="Snaps en cobertura" value={num(p.coverageSnaps)} sub="rol asignado por PFF" />
          ) : null}
          {p.routeSnaps >= 10 ? <Stat label="Rutas corridas" value={num(p.routeSnaps)} sub="rol asignado por PFF" /> : null}
          <Stat label="Velocidad máxima" value={p.topSpeed === null ? '—' : `${p.topSpeed} yd/s`} sub="pico en tracking a 10 Hz" />
          <Stat label="Aceleración máxima" value={p.topAccel === null ? '—' : `${p.topAccel} yd/s²`} sub="pico en tracking a 10 Hz" />
          <Stat
            label="Amonestaciones"
            value={num(p.penalties)}
            sub={Object.keys(p.penaltyKinds).length ? Object.entries(p.penaltyKinds).map(([k, v]) => `${k} (${v})`).join(' · ') : 'sin castigos marcados'}
          />
        </div>
      </section>

      {/* percentiles */}
      <section className="grid gap-8 border-t rule pt-6 md:grid-cols-2">
        <div>
          <h3 className="eyebrow mb-2">
            Contra sus pares · {p.peerGroup?.position} con 20+ snaps (n={p.peerGroup?.n})
          </h3>
          <div className="max-w-md">
            <Bar v={pr.plays ?? null} label="Volumen de snaps" />
            <Bar v={pr.topSpeed ?? null} label="Velocidad máxima" />
            <Bar v={pr.topAccel ?? null} label="Aceleración máxima" />
            <Bar v={pr.asvOnField ?? null} label="ASV con él en campo" />
            {isRusher ? <Bar v={pr.pressureRate ?? null} label="Tasa de presión" /> : null}
            {isQB ? <Bar v={pr.completionPct ?? null} label="Precisión de pase" /> : null}
            {isQB ? <Bar v={pr.yardsPerAttempt ?? null} label="Yardas por intento" /> : null}
          </div>
        </div>
        <div>
          <h3 className="eyebrow mb-2">Reparto de roles</h3>
          <div className="space-y-2">
            {([
              ['Pasador', p.passSnaps],
              ['Protección', p.blockSnaps],
              ['Ruta', p.routeSnaps],
              ['Rush', p.rushSnaps],
              ['Cobertura', p.coverageSnaps],
            ] as const)
              .filter(([, v]) => v > 0)
              .map(([k, v]) => (
                <div key={k}>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-ink2">{k}</span>
                    <span className="num text-dim">
                      {v} · {pct(v / Math.max(1, p.plays), 0)}
                    </span>
                  </div>
                  <div className="mt-1 h-[3px] w-full bg-track">
                    <div
                      className="h-[3px]"
                      style={{ width: `${(100 * v) / Math.max(1, p.plays)}%`, background: teamColor(p.team) }}
                    />
                  </div>
                </div>
              ))}
          </div>
          <p className="mt-4 text-[11px] leading-relaxed text-dim">
            Los percentiles comparan contra jugadores de la misma posición oficial con al menos 20 snaps de pase. El
            dataset cubre únicamente jugadas de pase, por lo que la carga de trabajo en jugadas de carrera y equipos
            especiales no aparece aquí.
          </p>
        </div>
      </section>
    </div>
  )
}
