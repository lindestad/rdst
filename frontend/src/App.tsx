import { useEffect } from "react";

import { api } from "./api/client";
import { CompareView } from "./components/CompareView";
import { Header } from "./components/Header";
import { LeftRail } from "./components/LeftRail";
import { MonthScrubber } from "./components/MonthScrubber";
import { NileMap } from "./components/NileMap";
import { RightRail } from "./components/RightRail";
import { ScenarioTray } from "./components/ScenarioTray";
import { useStore } from "./state/store";

export default function App() {
  const { setNodes, setSaved, compareMode } = useStore();

  useEffect(() => {
    api.nodes().then(setNodes).catch(console.error);
    api.listScenarios().then(setSaved).catch(console.error);
  }, [setNodes, setSaved]);

  return (
    <div className="h-screen flex flex-col bg-slate-900 text-slate-100 overflow-hidden">
      <Header />
      {compareMode ? (
        <div className="flex-1 min-h-0">
          <CompareView />
        </div>
      ) : (
        <div className="flex-1 min-h-0 grid grid-cols-[340px_1fr_320px]">
          <LeftRail />
          <div className="relative overflow-hidden">
            <NileMap />
            <MonthScrubber />
          </div>
          <RightRail />
        </div>
      )}
      <ScenarioTray />
    </div>
  );
}
