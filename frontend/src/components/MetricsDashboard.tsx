import type { SimulationData } from "../types/simulation"

interface Props {
  data: SimulationData
}

function StatusBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
      <div
        className={`h-2 rounded-full transition-all duration-500 ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function MetricRow({
  label,
  value,
  unit,
  good,
}: {
  label: string
  value: string | number
  unit?: string
  good?: boolean
}) {
  return (
    <div className="flex items-center justify-between border-b border-gray-800 py-1">
      <span className="text-sm text-gray-400">{label}</span>
      <span
        className={`font-mono text-sm font-semibold ${good === undefined ? "text-gray-200" : good ? "text-green-400" : "text-red-400"}`}
      >
        {value}
        {unit && <span className="ml-1 text-xs text-gray-500">{unit}</span>}
      </span>
    </div>
  )
}

function Card({
  title,
  icon,
  children,
}: {
  title: string
  icon: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-bold tracking-widest text-gray-300 uppercase">
        <span>{icon}</span>
        {title}
      </h3>
      {children}
    </div>
  )
}

export default function MetricsDashboard({ data }: Props) {
  const { status, weather, energy, water, crops, crew, nutrients, crises, score, greenhouse } = data

  if (data.loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="animate-pulse font-mono text-lg text-green-400">
          Connecting to simulation...
        </p>
      </div>
    )
  }

  const criticalCrises = crises?.crises.filter((c) => c.severity === "critical") ?? []
  const warningCrises = crises?.crises.filter((c) => c.severity === "warning") ?? []

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-mono text-2xl font-bold text-white">MISSION METRICS</h2>
          <p className="font-mono text-sm text-gray-500">
            Sol {status?.current_sol ?? "—"} / {status?.total_sols ?? 450} ·{" "}
            {status?.mission_phase ?? "unknown"}
          </p>
        </div>
        {score && (
          <div className="text-right">
            <div className="font-mono text-4xl font-bold text-green-400">
              {score.scores.overall_score}
            </div>
            <div className="text-xs tracking-widest text-gray-500 uppercase">Overall Score</div>
          </div>
        )}
      </div>

      {/* Active crises banner */}
      {(criticalCrises.length > 0 || warningCrises.length > 0) && (
        <div className="space-y-2">
          {criticalCrises.map((c) => (
            <div
              key={c.id}
              className="flex items-center gap-3 rounded-lg border border-red-700 bg-red-950 p-3"
            >
              <span className="text-lg text-red-400">⚠</span>
              <span className="font-mono text-sm font-semibold text-red-300 uppercase">
                {c.type.replace(/_/g, " ")}
              </span>
              {c.current_value != null && (
                <span className="ml-auto font-mono text-sm text-red-400">
                  {c.current_value.toFixed(1)} / threshold {c.threshold}
                </span>
              )}
            </div>
          ))}
          {warningCrises.map((c) => (
            <div
              key={c.id}
              className="flex items-center gap-3 rounded-lg border border-yellow-700 bg-yellow-950 p-3"
            >
              <span className="text-lg text-yellow-400">⚡</span>
              <span className="font-mono text-sm text-yellow-300">{c.type.replace(/_/g, " ")}</span>
            </div>
          ))}
        </div>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {/* Crew Nutrition */}
        <Card title="Crew Nutrition" icon="👨‍🚀">
          {crew ? (
            <div className="space-y-2">
              <div className="mb-1 flex justify-between text-xs text-gray-500">
                <span>Daily Calories</span>
                <span className="font-mono">
                  {crew.today.calories_consumed_kcal.toLocaleString()} /{" "}
                  {crew.today.calories_target_kcal.toLocaleString()} kcal
                </span>
              </div>
              <StatusBar
                value={crew.today.calories_consumed_kcal}
                max={crew.today.calories_target_kcal}
                color={
                  crew.today.calories_consumed_kcal >= crew.today.calories_target_kcal * 0.9
                    ? "bg-green-500"
                    : "bg-red-500"
                }
              />
              <div className="mt-2 mb-1 flex justify-between text-xs text-gray-500">
                <span>Daily Protein</span>
                <span className="font-mono">
                  {crew.today.protein_consumed_g}g / {crew.today.protein_target_g}g
                </span>
              </div>
              <StatusBar
                value={crew.today.protein_consumed_g}
                max={crew.today.protein_target_g}
                color={
                  crew.today.protein_consumed_g >= crew.today.protein_target_g * 0.9
                    ? "bg-blue-500"
                    : "bg-orange-500"
                }
              />
              <div className="space-y-0.5 pt-2">
                <MetricRow
                  label="From greenhouse"
                  value={`${crew.today.from_greenhouse_pct}%`}
                  good={crew.today.from_greenhouse_pct > 50}
                />
                <MetricRow
                  label="Stored food remaining"
                  value={crew.stored_food.remaining_days_at_current_rate}
                  unit="days"
                  good={crew.stored_food.remaining_days_at_current_rate > 60}
                />
                <MetricRow
                  label="Avg daily kcal (cumulative)"
                  value={crew.cumulative.avg_daily_kcal.toLocaleString()}
                  unit="kcal"
                />
                <MetricRow
                  label="Deficit days"
                  value={crew.cumulative.deficit_sols}
                  good={crew.cumulative.deficit_sols === 0}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-600 italic">No data</p>
          )}
        </Card>

        {/* Energy */}
        <Card title="Energy System" icon="⚡">
          {energy ? (
            <div className="space-y-2">
              <div className="mb-1 flex justify-between text-xs text-gray-500">
                <span>Battery</span>
                <span className="font-mono">{energy.battery_pct.toFixed(1)}%</span>
              </div>
              <StatusBar
                value={energy.battery_level_wh}
                max={energy.battery_capacity_wh}
                color={energy.battery_pct > 40 ? "bg-yellow-400" : "bg-red-500"}
              />
              <div className="space-y-0.5 pt-2">
                <MetricRow
                  label="Solar generation"
                  value={energy.solar_generation_wh.toLocaleString()}
                  unit="Wh"
                />
                <MetricRow
                  label="Total consumption"
                  value={energy.total_consumption_wh.toLocaleString()}
                  unit="Wh"
                />
                <MetricRow
                  label="Surplus"
                  value={energy.surplus_wh.toLocaleString()}
                  unit="Wh"
                  good={!energy.deficit}
                />
                <MetricRow
                  label="Deficit"
                  value={energy.deficit ? "YES" : "NO"}
                  good={!energy.deficit}
                />
                <MetricRow
                  label="Heating"
                  value={energy.breakdown.heating_wh.toLocaleString()}
                  unit="Wh"
                />
                <MetricRow
                  label="Lighting"
                  value={energy.breakdown.lighting_wh.toLocaleString()}
                  unit="Wh"
                />
                <MetricRow
                  label="Water recycling"
                  value={energy.breakdown.water_recycling_wh.toLocaleString()}
                  unit="Wh"
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-600 italic">No data</p>
          )}
        </Card>

        {/* Water */}
        <Card title="Water System" icon="💧">
          {water ? (
            <div className="space-y-2">
              <div className="mb-1 flex justify-between text-xs text-gray-500">
                <span>Reservoir</span>
                <span className="font-mono">
                  {water.reservoir_liters}L / {water.reservoir_capacity_liters}L
                </span>
              </div>
              <StatusBar
                value={water.reservoir_liters}
                max={water.reservoir_capacity_liters}
                color={
                  water.reservoir_liters / water.reservoir_capacity_liters > 0.4
                    ? "bg-blue-500"
                    : "bg-red-500"
                }
              />
              <div className="mt-2 mb-1 flex justify-between text-xs text-gray-500">
                <span>Filter health</span>
                <span className="font-mono">{water.filter_health_pct}%</span>
              </div>
              <StatusBar
                value={water.filter_health_pct}
                max={100}
                color={water.filter_health_pct > 60 ? "bg-teal-500" : "bg-orange-500"}
              />
              <div className="space-y-0.5 pt-2">
                <MetricRow
                  label="Recycling efficiency"
                  value={`${water.recycling_efficiency_pct.toFixed(1)}%`}
                  good={water.recycling_efficiency_pct >= 85}
                />
                <MetricRow
                  label="Daily crew use"
                  value={water.daily_crew_consumption_liters}
                  unit="L"
                />
                <MetricRow
                  label="Daily crop use"
                  value={water.daily_crop_consumption_liters}
                  unit="L"
                />
                <MetricRow
                  label="Daily net change"
                  value={water.daily_net_change_liters.toFixed(1)}
                  unit="L"
                  good={water.daily_net_change_liters >= 0}
                />
                <MetricRow
                  label="Days until critical"
                  value={water.days_until_critical}
                  good={water.days_until_critical > 30}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-600 italic">No data</p>
          )}
        </Card>

        {/* Weather */}
        <Card title="Mars Weather" icon="🌡️">
          {weather ? (
            <div className="space-y-0.5">
              <MetricRow label="Season" value={weather.season} />
              <MetricRow
                label="Min temp (external)"
                value={weather.min_temp_c.toFixed(1)}
                unit="°C"
              />
              <MetricRow
                label="Max temp (external)"
                value={weather.max_temp_c.toFixed(1)}
                unit="°C"
              />
              <MetricRow label="Pressure" value={weather.pressure_pa} unit="Pa" />
              <MetricRow
                label="Solar irradiance"
                value={weather.solar_irradiance_wm2}
                unit="W/m²"
                good={weather.solar_irradiance_wm2 > 300}
              />
              <MetricRow
                label="Dust opacity"
                value={weather.dust_opacity.toFixed(2)}
                good={weather.dust_opacity < 0.5}
              />
              <MetricRow label="Ls" value={`${weather.ls.toFixed(1)}°`} />
            </div>
          ) : (
            <p className="text-sm text-gray-600 italic">No data</p>
          )}
        </Card>

        {/* Greenhouse Environment */}
        <Card title="Greenhouse Zones" icon="🌿">
          {greenhouse ? (
            <div className="space-y-3">
              <MetricRow label="Total area" value={greenhouse.total_area_m2} unit="m²" />
              <MetricRow
                label="External temp"
                value={greenhouse.external_temp_c?.toFixed(1) ?? "—"}
                unit="°C"
              />
              {greenhouse.zones.map((z) => (
                <div key={z.zone_id} className="rounded-lg bg-gray-800 p-3">
                  <div className="mb-2 text-xs font-bold text-green-400">
                    ZONE {z.zone_id} · {z.area_m2} m²
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 text-xs">
                    <span className="text-gray-500">Temp</span>
                    <span className="text-right font-mono text-gray-200">
                      {z.temp_c.toFixed(1)} °C
                    </span>
                    <span className="text-gray-500">Humidity</span>
                    <span className="text-right font-mono text-gray-200">{z.humidity_pct}%</span>
                    <span className="text-gray-500">CO₂</span>
                    <span
                      className={`text-right font-mono ${z.co2_ppm >= 800 && z.co2_ppm <= 1200 ? "text-green-400" : "text-yellow-400"}`}
                    >
                      {z.co2_ppm} ppm
                    </span>
                    <span className="text-gray-500">PAR</span>
                    <span className="text-right font-mono text-gray-200">
                      {z.par_umol_m2s} µmol/m²/s
                    </span>
                    <span className="text-gray-500">Photoperiod</span>
                    <span className="text-right font-mono text-gray-200">
                      {z.photoperiod_hours}h
                    </span>
                    <span className="text-gray-500">Light</span>
                    <span
                      className={`text-right font-mono ${z.light_on ? "text-yellow-400" : "text-gray-600"}`}
                    >
                      {z.light_on ? "ON" : "OFF"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600 italic">No data</p>
          )}
        </Card>

        {/* Crops */}
        <Card title="Crop Status" icon="🌱">
          {crops ? (
            <div className="space-y-2">
              <div className="mb-2 flex justify-between text-xs text-gray-500">
                <span>{crops.crops.length} active batches</span>
                <span>
                  {Object.values(crops.available_area_per_zone).reduce((sum, v) => sum + v, 0)} m²
                  free
                </span>
              </div>
              {crops.crops.map((c) => (
                <div key={c.crop_id} className="rounded-lg bg-gray-800 p-2.5">
                  <div className="mb-1.5 flex items-start justify-between">
                    <div>
                      <span className="text-xs font-bold text-white capitalize">{c.type}</span>
                      <span className="ml-1 text-xs text-gray-500">· Zone {c.zone_id}</span>
                    </div>
                    <span
                      className={`font-mono text-xs font-bold ${c.health > 0.8 ? "text-green-400" : c.health > 0.5 ? "text-yellow-400" : "text-red-400"}`}
                    >
                      {(c.health * 100).toFixed(0)}% health
                    </span>
                  </div>
                  <div className="mb-1.5 flex gap-1">
                    <div className="flex-1">
                      <div className="mb-0.5 text-xs text-gray-600">
                        Growth {c.growth_pct.toFixed(1)}%
                      </div>
                      <StatusBar value={c.growth_pct} max={100} color="bg-green-600" />
                    </div>
                    <div className="flex-1">
                      <div className="mb-0.5 text-xs text-gray-600">Health</div>
                      <StatusBar
                        value={c.health * 100}
                        max={100}
                        color={
                          c.health > 0.8
                            ? "bg-green-500"
                            : c.health > 0.5
                              ? "bg-yellow-500"
                              : "bg-red-500"
                        }
                      />
                    </div>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>{c.area_m2} m²</span>
                    <span>Harvest sol {c.expected_harvest_sol}</span>
                    <span>~{c.estimated_calories_kcal.toLocaleString()} kcal</span>
                  </div>
                  {c.stress_indicators.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {c.stress_indicators.map((s, i) => (
                        <span
                          key={i}
                          className="rounded bg-red-950 px-1.5 py-0.5 text-xs text-red-300"
                        >
                          {s.type.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600 italic">No data</p>
          )}
        </Card>

        {/* Nutrients */}
        <Card title="Nutrient System" icon="🧪">
          {nutrients ? (
            <div className="space-y-3">
              <div className="mb-1 flex justify-between text-xs text-gray-500">
                <span>Stock remaining</span>
                <span className="font-mono">{nutrients.days_of_stock_remaining} days</span>
              </div>
              <StatusBar
                value={nutrients.nutrient_stock_remaining_pct}
                max={100}
                color={nutrients.nutrient_stock_remaining_pct > 40 ? "bg-purple-500" : "bg-red-500"}
              />
              {nutrients.zones.map((z) => (
                <div key={z.zone_id} className="rounded-lg bg-gray-800 p-3">
                  <div className="mb-2 text-xs font-bold text-purple-400">ZONE {z.zone_id}</div>
                  <div className="grid grid-cols-2 gap-x-4 text-xs">
                    <span className="text-gray-500">pH</span>
                    <span
                      className={`text-right font-mono ${z.solution_ph >= 5.5 && z.solution_ph <= 6.5 ? "text-green-400" : "text-yellow-400"}`}
                    >
                      {z.solution_ph.toFixed(1)}
                    </span>
                    <span className="text-gray-500">EC</span>
                    <span className="text-right font-mono text-gray-200">
                      {z.solution_ec_ms_cm.toFixed(1)} mS/cm
                    </span>
                    <span className="text-gray-500">DO₂</span>
                    <span
                      className={`text-right font-mono ${z.dissolved_o2_ppm > 5 ? "text-green-400" : "text-red-400"}`}
                    >
                      {z.dissolved_o2_ppm.toFixed(1)} ppm
                    </span>
                    <span className="text-gray-500">N / P / K</span>
                    <span className="text-right font-mono text-gray-200">
                      {z.nitrogen_ppm}/{z.phosphorus_ppm}/{z.potassium_ppm}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600 italic">No data</p>
          )}
        </Card>

        {/* Score */}
        {score && (
          <Card title="Mission Score" icon="🏆">
            <div className="space-y-3">
              {(
                [
                  { label: "Survival", val: score.scores.survival.score },
                  { label: "Nutrition", val: score.scores.nutrition.score },
                  { label: "Resources", val: score.scores.resource_efficiency.score },
                  { label: "Crisis Mgmt", val: score.scores.crisis_management.score },
                ] as const
              ).map((s) => (
                <div key={s.label}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-gray-400">{s.label}</span>
                    <span
                      className={`font-mono font-bold ${s.val >= 80 ? "text-green-400" : s.val >= 60 ? "text-yellow-400" : "text-red-400"}`}
                    >
                      {s.val}
                    </span>
                  </div>
                  <StatusBar
                    value={s.val}
                    max={100}
                    color={
                      s.val >= 80 ? "bg-green-500" : s.val >= 60 ? "bg-yellow-500" : "bg-red-500"
                    }
                  />
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
