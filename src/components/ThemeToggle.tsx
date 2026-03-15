import type { JSX } from "react";
import * as Switch from "@radix-ui/react-switch";
import { useTheme } from "../lib/ThemeContext";
import styles from "./ThemeToggle.module.css";

export default function ThemeToggle(): JSX.Element {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className={styles.themeToggle}>
      <span className={styles.icon} aria-hidden>
        ☀️
      </span>
      <Switch.Root
        className={styles.switchRoot}
        checked={theme === "dark"}
        onCheckedChange={toggleTheme}
        aria-label="Toggle dark mode"
      >
        <Switch.Thumb className={styles.switchThumb} />
      </Switch.Root>
      <span className={styles.icon} aria-hidden>
        🌙
      </span>
    </div>
  );
}
