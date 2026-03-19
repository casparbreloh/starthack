import type { CropsStatus, GreenhouseEnvironment, NutrientsStatus } from "../../types/simulation"
import PlantCell from "./PlantCell"

interface Props {
  crops: CropsStatus | null
  greenhouse: GreenhouseEnvironment | null
  nutrients: NutrientsStatus | null
}

export default function GreenhouseMap({ crops, greenhouse, nutrients }: Props) {
  const zones = greenhouse?.zones ?? []
  const allCrops = crops?.crops ?? []
  const totalArea = greenhouse?.total_area_m2 ?? 50
  const availableArea = crops?.available_area_m2 ?? 0

  return (
    <div
      className="flex flex-col overflow-hidden rounded-2xl"
      style={{
        background: "rgba(0,15,5,0.95)",
        border: "2px solid #15803d",
        boxShadow: "0 0 40px #15803d33, inset 0 0 60px rgba(0,30,0,0.5)",
        minHeight: "420px",
      }}
    >
      {/* Greenhouse header */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ background: "rgba(21,128,61,0.25)", borderBottom: "1px solid #15803d" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm text-green-400">🌿</span>
          <span className="font-mono text-sm font-bold tracking-widest text-green-400 uppercase">
            GREENHOUSE MODULE
          </span>
        </div>
        <div className="flex items-center gap-4 font-mono text-xs text-gray-400">
          <span>{totalArea} m² total</span>
          <span className={availableArea > 0 ? "text-green-500" : "text-gray-600"}>
            {availableArea} m² free
          </span>
        </div>
      </div>

      {/* Zone grid */}
      <div className="flex flex-1 gap-4 overflow-auto p-4">
        {zones.length === 0 && (
          <div className="flex flex-1 items-center justify-center">
            <p className="font-mono text-sm text-gray-600">Awaiting greenhouse data...</p>
          </div>
        )}

        {zones.map((zone) => {
          const zoneCrops = allCrops.filter((c) => c.zone_id === zone.zone_id)
          const nutrientZone = nutrients?.zones.find((n) => n.zone_id === zone.zone_id)
          const isHot = zone.temp_c > 25
          const isCold = zone.temp_c < 15
          const tempStatus = isHot ? "text-red-400" : isCold ? "text-blue-400" : "text-green-400"

          return (
            <div
              key={zone.zone_id}
              className="flex flex-col overflow-hidden rounded-xl"
              style={{
                flex: `0 0 ${Math.max(180, (zone.area_m2 / totalArea) * 100 * 4)}px`,
                background: "rgba(0,20,8,0.8)",
                border: "1px solid #166534",
                boxShadow: "inset 0 0 20px rgba(0,50,0,0.3)",
              }}
            >
              {/* Zone header */}
              <div
                className="flex items-center justify-between px-3 py-1.5"
                style={{ background: "rgba(22,101,52,0.3)", borderBottom: "1px solid #166534" }}
              >
                <span className="font-mono text-xs font-bold text-green-300">
                  ZONE {zone.zone_id}
                </span>
                <span className="font-mono text-xs text-gray-500">{zone.area_m2} m²</span>
              </div>

              {/* Zone env stats */}
              <div
                className="grid grid-cols-3 gap-1 px-3 py-2 font-mono text-xs"
                style={{ borderBottom: "1px solid #166534" }}
              >
                <div className="text-center">
                  <div className="text-gray-600">TEMP</div>
                  <div className={tempStatus}>{zone.temp_c.toFixed(1)}°</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-600">HUM</div>
                  <div className="text-blue-400">{zone.humidity_pct}%</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-600">CO₂</div>
                  <div
                    className={
                      zone.co2_ppm >= 800 && zone.co2_ppm <= 1200
                        ? "text-teal-400"
                        : "text-yellow-400"
                    }
                  >
                    {zone.co2_ppm}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-gray-600">PAR</div>
                  <div className="text-yellow-400">{zone.par_umol_m2s}</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-600">LIGHT</div>
                  <div className={zone.light_on ? "text-yellow-300" : "text-gray-600"}>
                    {zone.photoperiod_hours}h
                  </div>
                </div>
                {nutrientZone && (
                  <div className="text-center">
                    <div className="text-gray-600">pH</div>
                    <div
                      className={
                        nutrientZone.solution_ph >= 5.5 && nutrientZone.solution_ph <= 6.5
                          ? "text-purple-400"
                          : "text-red-400"
                      }
                    >
                      {nutrientZone.solution_ph.toFixed(1)}
                    </div>
                  </div>
                )}
              </div>

              {/* Scan lines overlay effect */}
              <div className="relative flex-1 p-3">
                <div
                  className="pointer-events-none absolute inset-0"
                  style={{
                    backgroundImage:
                      "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,255,50,0.015) 3px, rgba(0,255,50,0.015) 4px)",
                  }}
                />

                {/* Plants */}
                {zoneCrops.length > 0 ? (
                  <div className="relative z-10 flex flex-wrap gap-2">
                    {zoneCrops.map((crop) => (
                      <PlantCell key={crop.crop_id} crop={crop} />
                    ))}
                  </div>
                ) : (
                  <div className="relative z-10 flex h-full min-h-24 items-center justify-center">
                    <div className="text-center">
                      <div className="mb-1 text-3xl opacity-20">□</div>
                      <div className="font-mono text-xs text-gray-700">EMPTY</div>
                    </div>
                  </div>
                )}
              </div>

              {/* Light strip at bottom */}
              {zone.light_on && (
                <div
                  className="h-1"
                  style={{
                    background: "linear-gradient(90deg, transparent, #fef08a88, transparent)",
                    boxShadow: "0 0 8px #fef08a44",
                  }}
                />
              )}
            </div>
          )
        })}

        {/* Empty space indicator */}
        {availableArea > 0 && zones.length > 0 && (
          <div
            className="flex flex-col items-center justify-center rounded-xl"
            style={{
              flex: `0 0 ${Math.max(80, (availableArea / totalArea) * 100 * 4)}px`,
              border: "1px dashed #1f2937",
              background: "rgba(0,0,0,0.3)",
              minHeight: "100px",
            }}
          >
            <span className="text-3xl opacity-20">+</span>
            <span className="mt-1 font-mono text-xs text-gray-700">{availableArea} m²</span>
            <span className="font-mono text-xs text-gray-700">available</span>
          </div>
        )}
      </div>
    </div>
  )
}
