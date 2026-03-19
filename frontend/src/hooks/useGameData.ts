import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { api } from "@/lib/api";
import * as mock from "@/lib/mockData";
import type * as T from "@/types/game";

const REFETCH = 3000;

// Wrapper: try API, fall back to mock
function useApiWithFallback<R>(
  key: string,
  apiFn: () => Promise<R>,
  fallback: R,
  interval = REFETCH
): UseQueryResult<R> {
  return useQuery<R>({
    queryKey: [key],
    queryFn: async () => {
      try {
        return await apiFn();
      } catch {
        return fallback;
      }
    },
    refetchInterval: interval,
  });
}

export const useSimStatus = () => useApiWithFallback("sim-status", api.getSimStatus, mock.mockSimStatus);
export const useWeather = () => useApiWithFallback("weather", api.getWeather, mock.mockWeather);
export const useEnergy = () => useApiWithFallback("energy", api.getEnergy, mock.mockEnergy);
export const useWater = () => useApiWithFallback("water", api.getWater, mock.mockWater);
export const useGreenhouseEnv = () => useApiWithFallback("greenhouse-env", api.getGreenhouseEnv, mock.mockZones);
export const useCrops = () => useApiWithFallback("crops", api.getCrops, mock.mockCrops);
export const useNutrients = () => useApiWithFallback("nutrients", api.getNutrients, mock.mockNutrients);
export const useCrewHealth = () => useApiWithFallback("crew-health", api.getCrewHealth, mock.mockCrewHealth);
export const useCrewMembers = () => useApiWithFallback("crew-members", api.getCrewMembers, mock.mockCrewMembers);
export const useCrewNutrition = () => useApiWithFallback("crew-nutrition", api.getCrewNutrition, mock.mockCrewNutrition);
export const useEventLog = (sol = 0) => useApiWithFallback(`events-${sol}`, () => api.getEventLog(sol), mock.mockEvents);
export const useActiveCrises = () => useApiWithFallback("crises", api.getActiveCrises, [] as T.ActiveCrisis[]);
export const useScore = () => useApiWithFallback("score", api.getScore, mock.mockScore);
export const useWeatherHistory = () => useApiWithFallback("weather-history", () => api.getWeatherHistory(30), [] as T.WeatherHistoryEntry[], 10000);
