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
    <div
      className="bg-slate-900 text-slate-100"
      style={{
        height: "100vh",
        display: "grid",
        gridTemplateRows: "auto 1fr auto",
        gridTemplateColumns: "100%",
      }}
    >
      <Header />
      {compareMode ? (
        <div style={{ minHeight: 0 }}>
          <CompareView />
        </div>
      ) : (
        <div
          style={{
            minHeight: 0,
            display: "grid",
            gridTemplateColumns: "340px 1fr 320px",
            gridTemplateRows: "100%",
          }}
        >
          <LeftRail />
          <div
            style={{ position: "relative", overflow: "hidden", minHeight: 0 }}
          >
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
