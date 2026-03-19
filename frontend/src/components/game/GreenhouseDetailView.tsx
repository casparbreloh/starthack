import { motion } from "framer-motion"
import { ArrowLeft } from "lucide-react"

import healthyHerbs from "@/assets/crops/healthy_herbs.png"
import healthyLettuce from "@/assets/crops/healthy_lettuce.png"
// Reuse crop images
import healthyPotato from "@/assets/crops/healthy_potato.png"
import healthyRadish from "@/assets/crops/healthy_radish.png"
import plainBed from "@/assets/crops/plain.png"
import unhealthyHerbs from "@/assets/crops/unhealthy_herbs.png"
import unhealthyLettuce from "@/assets/crops/unhealthy_lettuce.png"
import unhealthyPotato from "@/assets/crops/unhealthy_potato.png"
import unhealthyRadish from "@/assets/crops/unhealthy_radish.png"
import greenhouseDome from "@/assets/greenhouse-dome.png"
import { useWater, useEnergy } from "@/hooks/useGameData"
import type { CropBatch, ZoneEnvironment, ZoneNutrients } from "@/types/game"

const CROP_IMAGES: Record<string, { healthy: string; unhealthy: string }> = {
  potato: { healthy: healthyPotato, unhealthy: unhealthyPotato },
  lettuce: { healthy: healthyLettuce, unhealthy: unhealthyLettuce },
  herbs: { healthy: healthyHerbs, unhealthy: unhealthyHerbs },
  radish: { healthy: healthyRadish, unhealthy: unhealthyRadish },
  soybean: { healthy: healthyHerbs, unhealthy: unhealthyHerbs },
}

function getCropImage(crop: CropBatch): string {
  const key = crop.crop_type.toLowerCase()
  const images = CROP_IMAGES[key]
  if (!images) return plainBed
  return crop.health_pct >= 60 ? images.healthy : images.unhealthy
}

interface GreenhouseDetailViewProps {
  zoneId: string
  crops: CropBatch[]
  zone?: ZoneEnvironment
  nutrients?: ZoneNutrients
  onBack: () => void
}

export function GreenhouseDetailView({
  zoneId,
  crops,
  zone,
  nutrients,
  onBack,
}: GreenhouseDetailViewProps) {
  const { data: water } = useWater()
  const { data: energy } = useEnergy()

  // API returns zone IDs as "A", "B", "C"; hotspots pass "zone_a", "zone_b", "zone_c"
  const apiZoneId = zoneId.replace("zone_", "").toUpperCase()
  const zoneCrops = crops.filter((c) => c.zone_id === apiZoneId)
  const label = apiZoneId
  const totalArea = zoneCrops.reduce((s, c) => s + c.area_m2, 0).toFixed(1)
  const avgHealth =
    zoneCrops.length > 0
      ? Math.round(zoneCrops.reduce((s, c) => s + c.health_pct, 0) / zoneCrops.length)
      : 0
  const avgGrowth =
    zoneCrops.length > 0
      ? Math.round(zoneCrops.reduce((s, c) => s + c.growth_pct, 0) / zoneCrops.length)
      : 0
  const totalYieldKg = zoneCrops.reduce((s, c) => s + c.yield_estimate_kg, 0).toFixed(1)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="relative h-full w-full overflow-hidden"
    >
      {/* Background: greenhouse dome */}
      <img
        src={greenhouseDome}
        alt="Greenhouse dome interior"
        className="h-full w-full object-cover"
        draggable={false}
      />
      <div className="absolute inset-0 bg-background/50" />

      {/* Back button */}
      <motion.button
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        onClick={onBack}
        className="absolute left-4 top-4 z-20 flex items-center gap-2 rounded-sm border border-border bg-card/80 px-3 py-2 backdrop-blur-sm transition-colors hover:bg-card"
      >
        <ArrowLeft className="h-4 w-4 text-foreground" />
        <span className="label-aerospace">BACK</span>
      </motion.button>

      {/* Zone title */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute inset-x-0 top-4 z-20 mx-auto w-fit rounded-sm border border-border bg-card/80 px-6 py-2 backdrop-blur-sm"
      >
        <span className="font-mono text-lg tracking-[0.2em] text-foreground">
          GREENHOUSE {label}
        </span>
      </motion.div>

      {/* Crop beds in center — diamond layout */}
      <div className="absolute inset-0 z-10 flex items-center justify-center">
        <div className="flex flex-col items-center">
          {zoneCrops[0] && <CropBed crop={zoneCrops[0]} index={0} />}
          <div className={`flex ${zoneCrops[0] ? "-mt-40" : ""}`}>
            {zoneCrops[1] && <CropBed crop={zoneCrops[1]} index={1} />}
            {zoneCrops[2] && <CropBed crop={zoneCrops[2]} index={2} />}
          </div>
          {zoneCrops[3] && (
            <div className={zoneCrops[1] || zoneCrops[2] ? "-mt-40" : ""}>
              <CropBed crop={zoneCrops[3]} index={3} />
            </div>
          )}
        </div>
      </div>

      {/* Left panel: Environment + Water + Energy */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.15 }}
        className="absolute left-4 top-20 z-20 flex w-52 flex-col gap-3 rounded-sm border border-border bg-card/80 px-4 py-3 backdrop-blur-sm"
      >
        {/* Environment */}
        <div>
          <span className="label-aerospace mb-2 block text-primary">ENVIRONMENT</span>
          {zone && (
            <div className="flex flex-col gap-1.5">
              <DataRow label="TEMP" value={`${zone.temp_c.toFixed(1)}°C`} />
              <DataRow label="HUMIDITY" value={`${zone.humidity_pct.toFixed(1)}%`} />
              <DataRow label="CO₂" value={`${zone.co2_ppm.toFixed(0)} ppm`} />
              <DataRow label="LIGHT" value={`${zone.par_light_umol.toFixed(0)} µmol`} />
              <DataRow label="PHOTOPERIOD" value={`${zone.photoperiod_hours}h`} />
            </div>
          )}
        </div>

        <div className="h-px bg-border" />

        {/* Water recycling */}
        <div>
          <span className="label-aerospace mb-2 block text-primary">WATER RECYCLING</span>
          {water ? (
            <div className="flex flex-col gap-1.5">
              <DataRow
                label="RESERVOIR"
                value={`${water.reservoir_level_pct.toFixed(1)}%`}
                color={
                  water.reservoir_level_pct > 40
                    ? "text-primary"
                    : water.reservoir_level_pct > 20
                      ? "text-amber-alert"
                      : "text-destructive"
                }
              />
              <DataRow
                label="RECYCLING EFF."
                value={`${water.recycling_efficiency_pct.toFixed(1)}%`}
              />
              <DataRow
                label="FILTER HEALTH"
                value={`${water.filter_health_pct.toFixed(1)}%`}
                color={water.filter_health_pct > 50 ? "text-primary" : "text-amber-alert"}
              />
              <DataRow label="DAILY USE" value={`${water.daily_consumption_l.toFixed(1)} L`} />
              <DataRow
                label="RECYCLED"
                value={`${water.daily_recycled_l.toFixed(1)} L`}
                color="text-primary"
              />
              <DataRow
                label="DAYS LEFT"
                value={`${water.days_until_critical.toFixed(0)}`}
                color={
                  water.days_until_critical > 30
                    ? "text-primary"
                    : water.days_until_critical > 10
                      ? "text-amber-alert"
                      : "text-destructive"
                }
              />
            </div>
          ) : (
            <span className="font-mono text-[10px] text-muted-foreground">—</span>
          )}
        </div>

        <div className="h-px bg-border" />

        {/* Energy */}
        <div>
          <span className="label-aerospace mb-2 block text-primary">ENERGY</span>
          {energy ? (
            <div className="flex flex-col gap-1.5">
              <DataRow
                label="SOLAR GEN."
                value={`${energy.solar_generation_kw.toFixed(2)} kW`}
                color="text-primary"
              />
              <DataRow
                label="BATTERY"
                value={`${energy.battery_pct.toFixed(1)}%`}
                color={
                  energy.battery_pct > 40
                    ? "text-primary"
                    : energy.battery_pct > 20
                      ? "text-amber-alert"
                      : "text-destructive"
                }
              />
              <DataRow label="HEATING" value={`${energy.consumption.heating_kw.toFixed(2)} kW`} />
              <DataRow label="LIGHTING" value={`${energy.consumption.lighting_kw.toFixed(2)} kW`} />
              <DataRow label="WATER SYS." value={`${energy.consumption.water_kw.toFixed(2)} kW`} />
              <DataRow
                label="SURPLUS"
                value={`${energy.surplus_deficit_kw.toFixed(2)} kW`}
                color={energy.surplus_deficit_kw >= 0 ? "text-primary" : "text-destructive"}
              />
            </div>
          ) : (
            <span className="font-mono text-[10px] text-muted-foreground">—</span>
          )}
        </div>
      </motion.div>

      {/* Right panel: Detailed crop cards */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.15 }}
        className="absolute bottom-16 right-4 top-20 z-20 flex w-56 flex-col gap-2 overflow-y-auto rounded-sm border border-border bg-card/80 px-4 py-3 backdrop-blur-sm"
      >
        {/* Zone summary header */}
        <div className="mb-1 flex items-baseline justify-between">
          <span className="label-aerospace text-primary">CROPS</span>
          <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
            {zoneCrops.length} beds · {totalYieldKg} kg est.
          </span>
        </div>

        {/* One card per crop */}
        {zoneCrops.map((c) => (
          <div
            key={c.crop_id}
            className="flex flex-col gap-1.5 rounded border border-border bg-background/40 px-3 py-2"
          >
            {/* Header row */}
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-[11px] font-bold text-foreground">
                {c.crop_type.toUpperCase()}
              </span>
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                {c.area_m2} M²
              </span>
            </div>

            {/* Growth bar */}
            <div>
              <div className="mb-0.5 flex items-baseline justify-between">
                <span className="label-aerospace">GROWTH</span>
                <span className="font-mono text-[10px] tabular-nums text-foreground">
                  {c.growth_pct.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-sm bg-secondary">
                <div
                  className="h-full rounded-sm bg-primary transition-all duration-500"
                  style={{ width: `${c.growth_pct}%` }}
                />
              </div>
            </div>

            {/* Health bar */}
            <div>
              <div className="mb-0.5 flex items-baseline justify-between">
                <span className="label-aerospace">HEALTH</span>
                <span
                  className={`font-mono text-[10px] tabular-nums ${c.health_pct >= 70 ? "text-primary" : c.health_pct >= 40 ? "text-amber-alert" : "text-destructive"}`}
                >
                  {c.health_pct.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-sm bg-secondary">
                <div
                  className={`h-full rounded-sm transition-all duration-500 ${c.health_pct >= 70 ? "bg-primary" : c.health_pct >= 40 ? "bg-amber-alert" : "bg-destructive"}`}
                  style={{ width: `${c.health_pct}%` }}
                />
              </div>
            </div>

            {/* Stress indicators */}
            <div className="flex flex-wrap gap-2">
              {c.stress_water > 0 && (
                <span
                  className={`font-mono text-[9px] tabular-nums ${c.stress_water > 0.5 ? "text-destructive" : "text-amber-alert"}`}
                >
                  H₂O:{(c.stress_water * 100).toFixed(0)}%
                </span>
              )}
              {c.stress_nutrient > 0 && (
                <span
                  className={`font-mono text-[9px] tabular-nums ${c.stress_nutrient > 0.5 ? "text-destructive" : "text-amber-alert"}`}
                >
                  NUT:{(c.stress_nutrient * 100).toFixed(0)}%
                </span>
              )}
              {c.stress_light > 0 && (
                <span
                  className={`font-mono text-[9px] tabular-nums ${c.stress_light > 0.5 ? "text-destructive" : "text-amber-alert"}`}
                >
                  LIT:{(c.stress_light * 100).toFixed(0)}%
                </span>
              )}
              {c.stress_temp > 0 && (
                <span
                  className={`font-mono text-[9px] tabular-nums ${c.stress_temp > 0.5 ? "text-destructive" : "text-amber-alert"}`}
                >
                  TMP:{(c.stress_temp * 100).toFixed(0)}%
                </span>
              )}
              {c.stress_water === 0 &&
                c.stress_nutrient === 0 &&
                c.stress_light === 0 &&
                c.stress_temp === 0 && (
                  <span className="font-mono text-[9px] text-primary">NO STRESS</span>
                )}
            </div>

            {/* Harvest & yield */}
            <div className="flex items-baseline justify-between border-t border-border pt-0.5">
              <div className="flex items-baseline gap-1">
                <span className="label-aerospace">HARVEST</span>
                <span className="font-mono text-[10px] tabular-nums text-foreground">
                  {c.days_to_harvest} SOLS
                </span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="label-aerospace">YIELD</span>
                <span className="font-mono text-[10px] tabular-nums text-primary">
                  {c.yield_estimate_kg.toFixed(1)} KG
                </span>
              </div>
            </div>
          </div>
        ))}

        {/* Nutrients section below crops */}
        {nutrients && (
          <>
            <div className="mt-1 h-px bg-border" />
            <span className="label-aerospace text-primary">NUTRIENTS</span>
            <div className="flex flex-col gap-1.5">
              <DataRow label="PH" value={`${nutrients.ph.toFixed(1)}`} />
              <DataRow label="EC" value={`${nutrients.ec_ms_cm.toFixed(2)} mS/cm`} />
              <DataRow label="N" value={`${nutrients.nitrogen_ppm.toFixed(0)} ppm`} />
              <DataRow label="P" value={`${nutrients.phosphorus_ppm.toFixed(0)} ppm`} />
              <DataRow label="K" value={`${nutrients.potassium_ppm.toFixed(0)} ppm`} />
              <DataRow label="Ca" value={`${nutrients.calcium_ppm.toFixed(0)} ppm`} />
              <DataRow label="Mg" value={`${nutrients.magnesium_ppm.toFixed(0)} ppm`} />
              <DataRow
                label="STOCK"
                value={`${nutrients.stock_remaining_pct.toFixed(1)}%`}
                color={nutrients.stock_remaining_pct > 50 ? "text-primary" : "text-amber-alert"}
              />
              <DataRow
                label="STOCK DAYS"
                value={`${nutrients.days_of_stock.toFixed(0)}`}
                color={nutrients.days_of_stock > 30 ? "text-primary" : "text-amber-alert"}
              />
            </div>
          </>
        )}
      </motion.div>
    </motion.div>
  )
}

function DataRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="label-aerospace">{label}</span>
      <span className={`font-mono text-xs tabular-nums ${color || "text-foreground"}`}>
        {value}
      </span>
    </div>
  )
}

function CropBed({ crop, index }: { crop: CropBatch; index: number }) {
  const img = getCropImage(crop)
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.08, type: "spring", stiffness: 400, damping: 30 }}
      className="relative flex items-center justify-center"
    >
      <img src={img} alt={`${crop.crop_type} bed`} className="h-auto w-[240px]" draggable={false} />
      <div className="absolute left-1/2 top-1/2 z-10 min-w-[90px] -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded border border-border bg-background/85 px-1.5 py-1 text-center backdrop-blur-sm">
        <div className="mb-0.5 font-mono text-[8px] leading-none text-foreground">
          {crop.crop_type.toUpperCase()}
        </div>
        <div className="mb-px flex items-center gap-1">
          <span className="w-[10px] text-right font-mono text-[7px] text-muted-foreground">G</span>
          <div className="h-1 flex-1 overflow-hidden rounded-sm bg-secondary">
            <div
              className="h-full rounded-sm bg-primary transition-all duration-500"
              style={{ width: `${crop.growth_pct}%` }}
            />
          </div>
          <span className="w-[22px] text-right font-mono text-[7px] tabular-nums text-foreground">
            {crop.growth_pct}%
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-[10px] text-right font-mono text-[7px] text-muted-foreground">HP</span>
          <div className="h-1 flex-1 overflow-hidden rounded-sm bg-secondary">
            <div
              className={`h-full rounded-sm transition-all duration-500 ${crop.health_pct >= 60 ? "bg-primary" : crop.health_pct >= 30 ? "bg-amber-alert" : "bg-destructive"}`}
              style={{ width: `${crop.health_pct}%` }}
            />
          </div>
          <span className="w-[22px] text-right font-mono text-[7px] tabular-nums text-foreground">
            {crop.health_pct}%
          </span>
        </div>
        <div className="mt-0.5 font-mono text-[7px] leading-none text-muted-foreground">
          {crop.days_to_harvest}d
        </div>
      </div>
    </motion.div>
  )
}
