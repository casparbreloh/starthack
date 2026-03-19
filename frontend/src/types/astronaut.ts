export type AstronautRole = "commander" | "botanist" | "engineer" | "scientist"

export type GameLocation = "exterior" | "greenhouse" | "control"

export interface Astronaut {
  id: string
  name: string
  rank: string
  role: AstronautRole
  roleTitle: string
  description: string
  accent: string
  accentGlow: string
  initials: string
}

export interface CommMessage {
  id: string
  sender: "system" | "advisor" | "player"
  text: string
  timestamp: number
}

export const CREW_MEMBERS: Astronaut[] = [
  {
    id: "chen",
    name: "CDR. CHEN",
    rank: "Commander",
    role: "commander",
    roleTitle: "Mission Commander",
    description: "Mission oversight & strategic decisions",
    accent: "#f59e0b",
    accentGlow: "rgba(245,158,11,0.3)",
    initials: "CC",
  },
  {
    id: "okafor",
    name: "DR. OKAFOR",
    rank: "Botanist",
    role: "botanist",
    roleTitle: "Lead Botanist",
    description: "Crop management & greenhouse operations",
    accent: "#4ade80",
    accentGlow: "rgba(74,222,128,0.3)",
    initials: "DO",
  },
  {
    id: "vasquez",
    name: "ENG. VASQUEZ",
    rank: "Systems Engineer",
    role: "engineer",
    roleTitle: "Systems Engineer",
    description: "Energy, water & infrastructure",
    accent: "#22d3ee",
    accentGlow: "rgba(34,211,238,0.3)",
    initials: "EV",
  },
  {
    id: "lindqvist",
    name: "SCI. LINDQVIST",
    rank: "Science Officer",
    role: "scientist",
    roleTitle: "Science Officer",
    description: "Research, nutrients & data analysis",
    accent: "#a78bfa",
    accentGlow: "rgba(167,139,250,0.3)",
    initials: "SL",
  },
]
