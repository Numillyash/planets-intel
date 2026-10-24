import React from "react";
import { createRoot } from "react-dom/client";
import "../src/styles.css";
import { PlayerActivityPanel } from "../src/features/map/PlayerActivityPanel";

createRoot(document.getElementById("root")!).render(
    <PlayerActivityPanel gameId={687568} throughTurn={15} embedded />,
);
