import { motion } from "framer-motion";
import { Thermometer, Gauge, Wind, Sun, CloudFog } from "lucide-react";
import type { WeatherCurrent } from "@/types/simulation";

interface WeatherPanelProps {
  weather: WeatherCurrent;
}

export function WeatherPanel({ weather }: WeatherPanelProps) {
  const stats = [
    { icon: Thermometer, label: "Temp", value: `${weather.temp_max_c}°C`, color: "" },
    { icon: Gauge, label: "Pres", value: `${weather.pressure_mbar}m`, color: "" },
    { icon: Wind, label: "CO₂", value: `${(weather.dust_opacity * 100).toFixed(0) || "95.3"}%`, color: "" },
    { icon: Sun, label: "Solar", value: `${weather.solar_irradiance_w_m2}`, color: "" },
    { icon: CloudFog, label: "Dust", value: weather.dust_opacity < 0.5 ? "LOW" : weather.dust_opacity < 1 ? "MED" : "HIGH", color: weather.dust_opacity >= 1 ? "text-amber-alert" : "" },
  ];

  return (
    <div className="flex flex-col gap-2">
      {stats.map((s, i) => (
        <motion.div
          key={s.label}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05, type: "spring", stiffness: 400, damping: 30 }}
          className="flex items-center gap-3"
        >
          <s.icon className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
          <span className="label-aerospace w-12">{s.label}</span>
          <span className={`font-mono text-sm tabular-nums text-foreground ${s.color}`}>
            {s.value}
          </span>
        </motion.div>
      ))}
    </div>
  );
}
