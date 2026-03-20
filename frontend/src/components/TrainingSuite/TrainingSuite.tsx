import { useState } from "react"

import { useTrainingSessions } from "@/hooks/useTrainingSessions"

import ResultsPanel from "./ResultsPanel"
import SessionCard from "./SessionCard"
import SpawnSessionForm from "./SpawnSessionForm"

export default function TrainingSuite() {
  const {
    sessions,
    sessionDetails,
    selectedSession,
    loading,
    error,
    startSession,
    stopSession,
    selectSession,
    fetchResults,
  } = useTrainingSessions()
  const [showSpawnForm, setShowSpawnForm] = useState(false)

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-border px-6 py-5 pr-36">
        <div className="flex items-center gap-4">
          <span className="font-mono text-sm font-bold tracking-[0.2em] text-foreground">
            OASIS
          </span>
          <span className="font-mono text-sm font-semibold uppercase tracking-[0.15em] text-muted-foreground">
            Training Suite
          </span>
        </div>

        <button
          type="button"
          onClick={() => setShowSpawnForm(true)}
          className="rounded border border-primary/30 bg-primary/10 px-4 py-1.5 font-mono text-xs font-semibold text-primary transition-colors hover:bg-primary/20"
        >
          New Training Session
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="border-b border-red-400/20 bg-red-400/5 px-6 py-2">
          <p className="font-mono text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Session grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <p className="font-mono text-sm text-muted-foreground">Loading sessions...</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="font-mono text-sm text-muted-foreground">
              No training sessions yet. Start one to begin.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {sessions.map((session) => (
              <SessionCard
                key={session.session_id}
                session={session}
                detail={sessionDetails[session.session_id]}
                onSelect={selectSession}
                onStop={stopSession}
              />
            ))}
          </div>
        )}
      </div>

      {/* Spawn form modal */}
      {showSpawnForm && (
        <SpawnSessionForm
          onSubmit={(config) => {
            void startSession(config)
            setShowSpawnForm(false)
          }}
          onCancel={() => setShowSpawnForm(false)}
        />
      )}

      {/* Results panel modal */}
      {selectedSession && (
        <ResultsPanel
          session={selectedSession}
          fetchResults={fetchResults}
          onClose={() => selectSession(null)}
        />
      )}
    </div>
  )
}
