import { Moon, Sun } from "lucide-react";
import { useTheme } from "../theme";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const lightOn = theme === "light";
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={lightOn ? "Turn light mode off" : "Turn light mode on"}
      title={lightOn ? "Light on — click for dark" : "Light off — click for light"}
      onClick={() => setTheme(lightOn ? "dark" : "light")}
    >
      <span className={`theme-toggle-opt ${lightOn ? "is-on" : ""}`}>
        <Sun size={14} strokeWidth={2} />
      </span>
      <span className={`theme-toggle-opt ${!lightOn ? "is-on" : ""}`}>
        <Moon size={14} strokeWidth={2} />
      </span>
    </button>
  );
}
