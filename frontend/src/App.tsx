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
    <div className="h-full grid grid-rows-[auto_1fr_auto] bg-slate-900 text-slate-100">
      <Header />
      {compareMode ? (
        <CompareView />
      ) : (
        <div className="grid grid-cols-[340px_1fr_320px] min-h-0">
          <LeftRail />
          <div className="relative min-h-0">
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
