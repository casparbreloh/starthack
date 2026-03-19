import { GameView } from "@/components/game/GameView";

const Index = () => {
  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <div className="flex-1 flex flex-col min-h-0">
        <GameView />
      </div>
    </div>
  );
};

export default Index;
