import { useEffect, useRef, useState } from 'react'
import type { Player, Slot, TeamProfile } from './lib'
import { asv100, num, pct, teamColor } from './lib'

/* ------------------------------------------------------------------ casco */
export function Helmet({
  team,
  jersey,
  size = 28,
  dim = false,
}: {
  team?: string
  jersey?: number | null
  size?: number
  dim?: boolean
}) {
  const c = dim ? '#9ea2a8' : teamColor(team)
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <path d="M4 18a12 11 0 0 1 24 0v3H4z" fill={c} />
      <path d="M4 21h15a4 4 0 0 1 0 5H8a4 4 0 0 1-4-5z" fill={c} opacity="0.55" />
      <text
        x="16"
        y="17.5"
        textAnchor="middle"
        fontSize="11"
        fontWeight="700"
        fill="#fff"
        fontFamily="ui-sans-serif, system-ui"
      >
        {jersey ?? ''}
      </text>
    </svg>
  )
}

/* ---------------------------------------------------------------- métricas */
export function Stat({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub?: string
  accent?: boolean
}) {
  return (
    <div className="border-t rule pt-2">
      <div className="eyebrow">{label}</div>
      <div
        className={`num mt-1 text-2xl leading-none tracking-tight ${
          accent ? 'text-[#14161a]' : 'text-[#14161a]'
        }`}
      >
        {value}
      </div>
      {sub ? <div className="mt-1 text-[11px] leading-snug text-[#6b6f76]">{sub}</div> : null}
    </div>
  )
}

export function Bar({ v, label }: { v: number | null; label: string }) {
  const w = v === null ? 0 : Math.max(2, Math.min(100, v))
  return (
    <div className="py-1.5">
      <div className="flex items-baseline justify-between text-[11px]">
        <span className="text-[#43474d]">{label}</span>
        <span className="num text-[#6b6f76]">{v === null ? 'n/d' : `P${v.toFixed(0)}`}</span>
      </div>
      <div className="mt-1 h-[3px] w-full bg-[#e6e4de]">
        <div className="h-[3px] bg-[#14161a]" style={{ width: `${w}%` }} />
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- campo/mapa */
const X0 = -14
const X1 = 16
const FW = 53.3

export function FieldMap({
  lineup,
  onOpen,
  team,
}: {
  lineup: Slot[]
  team: string
  onOpen: (id: number) => void
}) {
  const [hover, setHover] = useState<Slot | null>(null)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const box = useRef<HTMLDivElement>(null)

  const sx = (x: number) => ((x - X0) / (X1 - X0)) * 100
  const sy = (y: number) => (1 - y / FW) * 100

  return (
    <div ref={box} className="relative w-full select-none">
      <div className="relative w-full overflow-hidden border rule bg-[#1b1e22]" style={{ aspectRatio: '30 / 24' }}>
        <svg viewBox={`0 0 ${X1 - X0} ${FW}`} className="absolute inset-0 h-full w-full" preserveAspectRatio="none">
          {Array.from({ length: X1 - X0 + 1 }, (_, i) => X0 + i).map((x) =>
            x % 5 === 0 ? (
              <line
                key={x}
                x1={x - X0}
                x2={x - X0}
                y1="0"
                y2={FW}
                stroke="#ffffff"
                strokeOpacity={x === 0 ? 0 : 0.14}
                strokeWidth="0.1"
              />
            ) : null,
          )}
          <line x1={-X0} x2={-X0} y1="0" y2={FW} stroke="#f5c243" strokeOpacity="0.75" strokeWidth="0.16" />
          <line x1="0" x2={X1 - X0} y1="1" y2="1" stroke="#fff" strokeOpacity="0.18" strokeWidth="0.1" />
          <line x1="0" x2={X1 - X0} y1={FW - 1} y2={FW - 1} stroke="#fff" strokeOpacity="0.18" strokeWidth="0.1" />
        </svg>

        <div className="absolute left-2 top-2 text-[9px] uppercase tracking-[0.14em] text-white/45">
          Línea de golpeo
        </div>
        <div className="absolute bottom-2 right-2 text-[9px] uppercase tracking-[0.14em] text-white/45">
          Avance →
        </div>

        {lineup.map((p) => {
          const defense = p.unit === 'DEF'
          return (
            <button
              key={`${p.slot}-${p.nflId}`}
              onClick={() => onOpen(p.nflId)}
              onMouseEnter={(e) => {
                const r = box.current?.getBoundingClientRect()
                setHover(p)
                setPos({ x: e.clientX - (r?.left ?? 0), y: e.clientY - (r?.top ?? 0) })
              }}
              onMouseMove={(e) => {
                const r = box.current?.getBoundingClientRect()
                setPos({ x: e.clientX - (r?.left ?? 0), y: e.clientY - (r?.top ?? 0) })
              }}
              onMouseLeave={() => setHover(null)}
              className="absolute -translate-x-1/2 -translate-y-1/2 transition-transform duration-150 hover:scale-110 focus:outline-none focus:ring-1 focus:ring-[#f5c243]"
              style={{ left: `${sx(p.x)}%`, top: `${sy(p.y)}%` }}
              title={`${p.name} · ${p.slot}`}
            >
              <div className="flex flex-col items-center gap-0.5">
                <Helmet team={p.team} jersey={p.jersey} size={26} dim={defense} />
                <span className="whitespace-nowrap rounded-sm bg-black/55 px-1 text-[8px] font-medium leading-[12px] text-white/90">
                  {p.slot}
                </span>
              </div>
            </button>
          )
        })}

        {hover ? (
          <div
            className="pointer-events-none absolute z-20 w-56 border border-[#2c3038] bg-[#0f1114]/96 p-3 text-white shadow-xl fade-in"
            style={{
              left: Math.min(Math.max(pos.x + 14, 4), 520),
              top: Math.max(pos.y - 10, 4),
            }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="text-[13px] font-semibold leading-tight">{hover.name}</div>
              <div className="num text-[11px] text-[#f5c243]">#{hover.jersey ?? '—'}</div>
            </div>
            <div className="mt-0.5 text-[10px] uppercase tracking-[0.1em] text-white/50">
              {hover.position} · alineado {hover.slot} · {hover.role}
            </div>
            <dl className="mt-2 space-y-1 text-[11px]">
              <Row k="Snaps en el acomodo" v={String(hover.snaps)} />
              <Row k="Dominio del puesto" v={pct(hover.slotShare, 0)} />
              <Row k="Posición media" v={`${hover.x >= 0 ? '+' : ''}${hover.x.toFixed(1)} yd · ${hover.y.toFixed(1)} yd`} />
            </dl>
            <div className="mt-2 border-t border-white/10 pt-1.5 text-[9px] uppercase tracking-[0.12em] text-[#f5c243]">
              Clic para ver el perfil
            </div>
          </div>
        ) : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-[10px] text-[#6b6f76]">
        <span>Posición promedio en el frame del snap, normalizada a atacar hacia la derecha.</span>
        <span className="flex items-center gap-1.5">
          <Helmet team={team} jersey={null} size={14} /> ataque
        </span>
        <span className="flex items-center gap-1.5">
          <Helmet jersey={null} size={14} dim /> defensa
        </span>
      </div>
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-white/55">{k}</dt>
      <dd className="num">{v}</dd>
    </div>
  )
}

/* ---------------------------------------------------------------- tablas */
export function LineupTable({
  data,
  onOpen,
}: {
  data: TeamProfile
  onOpen: (id: number) => void
}) {
  const off = data.lineup.filter((p) => p.unit !== 'DEF')
  const def = data.lineup.filter((p) => p.unit === 'DEF')
  const groups = def.length ? [['Unidad ofensiva', off], ['Unidad defensiva', def]] as const : [['En el acomodo', off]] as const

  return (
    <div className="space-y-6">
      {groups.map(([title, rows]) => (
        <div key={title}>
          <h4 className="eyebrow mb-2">{title}</h4>
          <table className="w-full border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-y rule text-[10px] uppercase tracking-[0.1em] text-[#6b6f76]">
                <th className="w-14 py-2 font-medium">#</th>
                <th className="py-2 font-medium">Alineación</th>
                <th className="py-2 font-medium">Jugador</th>
                <th className="hidden py-2 font-medium sm:table-cell">Pos.</th>
                <th className="py-2 text-right font-medium">Snaps</th>
                <th className="hidden py-2 text-right font-medium md:table-cell">Dominio</th>
              </tr>
            </thead>
            <tbody>
              {(rows as Slot[]).map((p) => (
                <tr
                  key={`${p.slot}-${p.nflId}`}
                  onClick={() => onOpen(p.nflId)}
                  className="cursor-pointer border-b rule transition-colors hover:bg-[#edebe5]"
                >
                  <td className="py-1.5">
                    <Helmet team={p.team} jersey={p.jersey} size={24} dim={p.unit === 'DEF'} />
                  </td>
                  <td className="num py-1.5 text-[#43474d]">{p.slot}</td>
                  <td className="py-1.5 font-medium">{p.name}</td>
                  <td className="hidden py-1.5 text-[#6b6f76] sm:table-cell">{p.position}</td>
                  <td className="num py-1.5 text-right">{p.snaps}</td>
                  <td className="num hidden py-1.5 text-right text-[#6b6f76] md:table-cell">
                    {pct(p.slotShare, 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      <div>
        <h4 className="eyebrow mb-1">Fuera del acomodo</h4>
        <p className="mb-2 max-w-xl text-[11px] text-[#6b6f76]">
          Jugadores con snaps de pase para {data.team} en la temporada que no entran en este acomodo óptimo.
          Ordenados por volumen de jugadas.
        </p>
        <div className="max-h-72 overflow-y-auto border-y rule">
          <table className="w-full border-collapse text-left text-[13px]">
            <tbody>
              {data.inactive.map((p) => (
                <tr
                  key={p.nflId}
                  onClick={() => onOpen(p.nflId)}
                  className="cursor-pointer border-b rule transition-colors last:border-0 hover:bg-[#edebe5]"
                >
                  <td className="w-14 py-1.5">
                    <Helmet team={p.team} jersey={p.jersey} size={22} dim />
                  </td>
                  <td className="py-1.5 text-[#43474d]">{p.name}</td>
                  <td className="py-1.5 text-[#6b6f76]">{p.position}</td>
                  <td className="num py-1.5 pr-1 text-right text-[#6b6f76]">{p.plays} snaps</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* --------------------------------------------------------- perfil jugador */
export function PlayerAvatar({ p, size = 168 }: { p: Player; size?: number }) {
  const c = teamColor(p.team)
  return (
    <svg width={size} height={size} viewBox="0 0 120 140" className="shrink-0 border rule bg-[#edebe5]">
      <rect width="120" height="140" fill="#e9e7e1" />
      <g>
        <path d="M26 140c0-26 15-40 34-40s34 14 34 40z" fill={c} />
        <path d="M54 102h12v10H54z" fill={c} opacity="0.8" />
        <circle cx="60" cy="74" r="20" fill="#c9c6be" />
        <path d="M36 70a24 22 0 0 1 48 0v7H36z" fill={c} />
        <path d="M36 77h28a7 7 0 0 1 0 11H44a8 8 0 0 1-8-11z" fill={c} opacity="0.5" />
        <text
          x="60"
          y="134"
          textAnchor="middle"
          fontSize="22"
          fontWeight="800"
          fill="#fff"
          fontFamily="ui-sans-serif, system-ui"
        >
          {p.jersey ?? ''}
        </text>
      </g>
    </svg>
  )
}

/* ------------------------------------------------------------ chat Rusher */
export function RusherMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <path d="M4 19a12 11 0 0 1 24 0v2H4z" fill="#f5c243" />
      <path d="M4 21h14a4 4 0 0 1 0 5H8a4 4 0 0 1-4-5z" fill="#f5c243" opacity="0.55" />
      <circle cx="11.5" cy="16" r="1.6" fill="#14161a" />
      <circle cx="20.5" cy="16" r="1.6" fill="#14161a" />
    </svg>
  )
}

type Msg = { role: 'user' | 'bot'; text: string; tools?: { name: string }[] }

export function Rusher({ enabled, quota }: { enabled: boolean; quota: number }) {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: 'bot',
      text: 'Soy Rusher. Consulto directamente las métricas calculadas: pregúntame por el acomodo óptimo de un equipo, por un jugador, o por el ranking ASV de la liga.',
    },
  ])
  const [val, setVal] = useState('')
  const [busy, setBusy] = useState(false)
  const [left, setLeft] = useState(quota)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => setLeft(quota), [quota])
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth' }), [msgs, open])

  async function send() {
    const q = val.trim()
    if (!q || busy) return
    setVal('')
    setMsgs((m) => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const r = await fetch('api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: q }),
      })
      const d = await r.json()
      if (typeof d.remaining === 'number') setLeft(d.remaining)
      setMsgs((m) => [...m, { role: 'bot', text: d.reply ?? d.message ?? 'Sin respuesta.', tools: d.tools }])
    } catch {
      setMsgs((m) => [
        ...m,
        { role: 'bot', text: 'El servicio de chat no está disponible en este momento. El análisis del tablero no depende de la IA.' },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 border border-[#14161a] bg-[#14161a] px-4 py-2.5 text-[12px] font-medium text-white shadow-lg transition-colors hover:bg-[#23262b]"
      >
        <RusherMark size={18} />
        Rusher
        <span className="num text-[10px] text-[#f5c243]">{left}/{quota}</span>
      </button>

      {open ? (
        <div className="fixed bottom-20 right-5 z-40 flex h-[26rem] w-[min(23rem,calc(100vw-2.5rem))] flex-col border rule bg-white shadow-2xl fade-in">
          <div className="flex items-center justify-between border-b rule px-3 py-2.5">
            <div className="flex items-center gap-2">
              <RusherMark size={20} />
              <div>
                <div className="text-[12px] font-semibold leading-none">Rusher</div>
                <div className="text-[9px] uppercase tracking-[0.1em] text-[#6b6f76]">
                  Asistente sobre métricas ASV
                </div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="px-1 text-[#6b6f76] hover:text-black" aria-label="Cerrar">
              ✕
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
            {!enabled ? (
              <p className="border-l-2 border-[#f5c243] bg-[#fdf8ec] p-2 text-[11px] text-[#43474d]">
                Los servicios de chat no están disponibles en este momento. Todo el análisis del tablero sigue
                funcionando sin IA.
              </p>
            ) : null}
            {msgs.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'text-right' : ''}>
                <div
                  className={`inline-block max-w-[92%] px-2.5 py-2 text-left text-[12px] leading-relaxed ${
                    m.role === 'user' ? 'bg-[#14161a] text-white' : 'border rule bg-[#f7f7f5]'
                  }`}
                >
                  {m.text}
                </div>
                {m.tools?.length ? (
                  <div className="mt-1 text-[9px] uppercase tracking-[0.1em] text-[#8a8e95]">
                    Consultó: {m.tools.map((t) => t.name).join(' · ')}
                  </div>
                ) : null}
              </div>
            ))}
            {busy ? <div className="text-[11px] text-[#6b6f76]">Consultando métricas…</div> : null}
            <div ref={end} />
          </div>

          <div className="border-t rule p-2">
            <div className="flex gap-2">
              <input
                value={val}
                onChange={(e) => setVal(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send()}
                placeholder="¿Cuál es el mejor acomodo ofensivo de KC?"
                className="w-full border rule bg-[#f7f7f5] px-2 py-1.5 text-[12px] outline-none focus:border-[#14161a]"
              />
              <button
                onClick={send}
                disabled={busy || left <= 0}
                className="border border-[#14161a] bg-[#14161a] px-3 text-[11px] font-medium text-white disabled:opacity-40"
              >
                Enviar
              </button>
            </div>
            <div className="mt-1.5 text-[9px] text-[#8a8e95]">
              {left} de {quota} consultas disponibles hoy. La bolsa se renueva a las 00:00 (CDMX).
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}

export const fmt = { pct, asv100, num }
