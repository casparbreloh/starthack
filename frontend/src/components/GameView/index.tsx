import type { SimulationData } from "../../types/simulation"
import AstronautHUD from "./AstronautHUD"
import GreenhouseMap from "./GreenhouseMap"
import ResourceBars from "./ResourceBars"

interface Props {
  data: SimulationData
}

function WeatherBackground({ dustOpacity }: { dustOpacity: number }) {
  const isStorm = dustOpacity > 0.7
  const isDusty = dustOpacity > 0.4
  const stormAlpha = Math.min(0.6, dustOpacity * 0.7)

  return (
    <>
      {/* Mars sky gradient */}
      <div
        className="absolute inset-0"
        style={{
          background: isStorm
            ? `radial-gradient(ellipse at 50% 0%, rgba(180,80,20,${stormAlpha}) 0%, rgba(100,30,5,0.7) 40%, rgba(5,5,10,0.95) 100%)`
            : isDusty
              ? `radial-gradient(ellipse at 50% 0%, rgba(160,60,20,0.35) 0%, rgba(60,20,5,0.5) 40%, rgba(5,5,10,0.95) 100%)`
              : `radial-gradient(ellipse at 50% 0%, rgba(120,40,15,0.25) 0%, rgba(40,10,5,0.4) 40%, rgba(3,5,10,0.98) 100%)`,
        }}
      />

      {/* Stars (only visible when clear) */}
      {!isStorm && (
        <div className="absolute inset-0 overflow-hidden">
          {Array.from({ length: 40 }).map((_, i) => (
            <div
              key={i}
              className="absolute rounded-full"
              style={{
                width: Math.random() > 0.8 ? "2px" : "1px",
                height: Math.random() > 0.8 ? "2px" : "1px",
                background: "white",
                opacity: (0.3 + Math.random() * 0.7) * (1 - dustOpacity * 0.8),
                left: `${(i * 37 + 13) % 100}%`,
                top: `${(i * 23 + 7) % 45}%`,
              }}
            />
          ))}
        </div>
      )}

      {/* Mars horizon */}
      <div
        className="absolute right-0 bottom-0 left-0"
        style={{
          height: "35%",
          background: isStorm
            ? "linear-gradient(0deg, rgba(120,50,10,0.6) 0%, transparent 100%)"
            : "linear-gradient(0deg, rgba(80,30,5,0.4) 0%, transparent 100%)",
        }}
      />

      {/* Dust storm overlay */}
      {isDusty && (
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: `radial-gradient(ellipse at 50% 50%, rgba(200,100,30,${stormAlpha * 0.4}) 0%, transparent 70%)`,
          }}
        />
      )}

      {/* Storm label */}
      {isStorm && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2">
          <span className="animate-pulse font-mono text-xs font-bold tracking-widest text-orange-400 uppercase">
            ⚠ DUST STORM · OPACITY {(dustOpacity * 100).toFixed(0)}%
          </span>
        </div>
      )}
    </>
  )
}

export default function GameView({ data }: Props) {
  const { status, weather, energy, water, crops, greenhouse, nutrients, crew, crises } = data
  const dustOpacity = weather?.dust_opacity ?? 0.2
  const sol = status?.current_sol ?? 0
  const totalSols = status?.total_sols ?? 450
  const missionPct = (sol / totalSols) * 100

  if (data.loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <div className="animate-pulse font-mono text-2xl text-green-400">◉</div>
        <p className="font-mono text-sm tracking-widest text-green-600 uppercase">
          Connecting to Simulation
        </p>
      </div>
    )
  }

  const offline = !status && !weather && !energy

  return (
    <div
      className="relative flex min-h-screen flex-col overflow-hidden"
      style={{ fontFamily: "'Courier New', Courier, monospace" }}
    >
      {/* Mars background */}
      <WeatherBackground dustOpacity={dustOpacity} />

      {/* Content layer */}
      <div className="relative z-10 flex h-full min-h-screen flex-col gap-4 p-4">
        {/* Top bar */}
        <div className="flex items-start justify-between gap-4">
          {/* Astronaut HUD — top left */}
          <AstronautHUD crew={crew} crises={crises} />

          {/* Mission status — center top */}
          <div className="flex flex-1 flex-col items-center gap-1">
            <div
              className="rounded-xl px-6 py-2 text-center"
              style={{
                background: "rgba(0,10,5,0.85)",
                border: "1px solid #065f46",
                boxShadow: "0 0 20px #065f4633",
              }}
            >
              <div className="font-mono text-xs tracking-widest text-gray-500 uppercase">
                Mars Greenhouse Station
              </div>
              <div className="font-mono text-3xl font-bold text-green-400">SOL {sol}</div>
              <div className="font-mono text-xs text-gray-500">
                of {totalSols} · {weather?.season ?? "—"}
              </div>
            </div>
            {/* Mission progress bar */}
            <div
              className="w-64 overflow-hidden rounded-full"
              style={{ height: "6px", background: "rgba(0,0,0,0.5)", border: "1px solid #1f2937" }}
            >
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{
                  width: `${missionPct}%`,
                  background: "linear-gradient(90deg, #22c55e, #16a34a)",
                  boxShadow: "0 0 8px #22c55e66",
                }}
              />
            </div>
            <div className="font-mono text-xs text-gray-600">
              {missionPct.toFixed(1)}% mission complete
            </div>
          </div>

          {/* Weather panel — top right */}
          <div
            className="overflow-hidden rounded-xl text-right"
            style={{
              background: "rgba(0,10,5,0.92)",
              border: "1px solid #1f2937",
              minWidth: "180px",
            }}
          >
            <div
              className="px-3 py-1.5 font-mono text-xs tracking-widest text-gray-400 uppercase"
              style={{ background: "rgba(30,30,30,0.4)", borderBottom: "1px solid #1f2937" }}
            >
              Mars Weather
            </div>
            <div className="space-y-1 p-3 font-mono text-xs">
              <div className="flex justify-between gap-4">
                <span className="text-gray-600">EXT TEMP</span>
                <span className="text-blue-400">
                  {weather?.min_temp_c.toFixed(0)}° / {weather?.max_temp_c.toFixed(0)}°C
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-gray-600">PRESSURE</span>
                <span className="text-gray-300">{weather?.pressure_pa ?? "—"} Pa</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-gray-600">SOLAR</span>
                <span className="text-yellow-400">{weather?.solar_irradiance_wm2 ?? "—"} W/m²</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-gray-600">DUST</span>
                <span className={dustOpacity > 0.5 ? "text-orange-400" : "text-gray-400"}>
                  {(dustOpacity * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Greenhouse — main area */}
        {offline ? (
          <div
            className="flex flex-1 items-center justify-center rounded-2xl"
            style={{ border: "2px dashed #1f2937", background: "rgba(0,0,0,0.3)" }}
          >
            <div className="space-y-2 text-center">
              <div className="text-5xl opacity-30">🌱</div>
              <p className="font-mono text-sm tracking-widest text-gray-600 uppercase">
                Simulation Offline
              </p>
              <p className="font-mono text-xs text-gray-700">Start the simulation to connect</p>
            </div>
          </div>
        ) : (
          <div className="flex-1">
            <GreenhouseMap crops={crops} greenhouse={greenhouse} nutrients={nutrients} />
          </div>
        )}

        {/* Resource bars — bottom */}
        <ResourceBars energy={energy} water={water} nutrients={nutrients} />

        {/* Energy micro-detail */}
        {energy && (
          <div
            className="flex items-center gap-4 rounded-lg px-4 py-2 font-mono text-xs text-gray-600"
            style={{ background: "rgba(0,5,0,0.7)", border: "1px solid #111" }}
          >
            <span className="text-gray-500">POWER</span>
            <span>HEAT {energy.breakdown.heating_wh.toLocaleString()}Wh</span>
            <span>LIGHT {energy.breakdown.lighting_wh.toLocaleString()}Wh</span>
            <span>H₂O {energy.breakdown.water_recycling_wh.toLocaleString()}Wh</span>
            <span>PUMPS {energy.breakdown.nutrient_pumps_wh.toLocaleString()}Wh</span>
            <span className="ml-auto">
              GEN {energy.solar_generation_wh.toLocaleString()}Wh SOLAR
            </span>
            <span className={energy.deficit ? "animate-pulse text-red-400" : "text-green-600"}>
              {energy.deficit ? "⚠ DEFICIT" : "✓ BALANCED"}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
