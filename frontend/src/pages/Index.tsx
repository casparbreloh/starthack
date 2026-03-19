import { GameView } from "@/components/game/GameView"

const Index = () => {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <div className="flex min-h-0 flex-1 flex-col">
        <GameView />
      </div>
    </div>
  )
}

export default Index
