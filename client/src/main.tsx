import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";

try {
	let theme = localStorage.getItem("theme");
	if (theme === "system" || !theme) {
		theme = window.matchMedia("(prefers-color-scheme: dark)").matches
			? "dark"
			: "light";
	}
	document.documentElement.classList.add(theme);
} catch {
	// Theme initialization is optional; next-themes will apply the default.
}

createRoot(document.getElementById("root")!).render(
	<BrowserRouter>
		<App />
	</BrowserRouter>,
);
