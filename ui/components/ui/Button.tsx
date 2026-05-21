/**
 * Button — primary / secondary / ghost / dark variants.
 * The CSS lives in styles/relay.css (`rl-btn*`); this is just the typed
 * React wrapper.
 */
import { ButtonHTMLAttributes, forwardRef, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "dark";
export type ButtonSize = "default" | "large";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
}

const variantClass: Record<ButtonVariant, string> = {
  primary: "rl-btn-primary",
  secondary: "rl-btn-secondary",
  ghost: "rl-btn-ghost",
  dark: "rl-btn-dark",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "secondary", size = "default", className, children, ...props }, ref) => {
    const classes = [
      "rl-btn",
      variantClass[variant],
      size === "large" ? "rl-btn-lg" : "",
      className ?? "",
    ]
      .filter(Boolean)
      .join(" ");
    return (
      <button ref={ref} className={classes} {...props}>
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";
