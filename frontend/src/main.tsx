import React from "react";
import ReactDOM from "react-dom/client";

import "./styles.css";


function App() {
    return (
        <main className="app">
            <header>
                <h1>Planets.nu Intel</h1>
                <p>Intelligence and analytics client</p>
            </header>

            <section className="panel">
                <h2>MVP 0.1</h2>

                <p>
                    Backend connection, public game data and
                    strategic map will appear here.
                </p>
            </section>
        </main>
    );
}


ReactDOM
    .createRoot(document.getElementById("root")!)
    .render(
        <React.StrictMode>
            <App />
        </React.StrictMode>,
    );
