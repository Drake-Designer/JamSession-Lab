tailwind.config = {
    theme: {
        extend: {
            colors: {
                // Core brand palette — always dark, matching logo identity
                jam: {
                    black: "#000000",
                    red: "#E63946", // ~5.5:1 on black — passes WCAG AA for text
                    "red-hover": "#FF4D5A", // Brighter hover — still AA on black
                    "red-muted": "#B82D38", // Darker red for borders/secondary accents
                    white: "#FFFFFF",
                    grey: "#1A1A1A", // Card/section backgrounds
                    "grey-light": "#262626", // Subtle elevation, borders
                    muted: "#A3A3A3", // Body copy on dark backgrounds (~7.5:1 on black)
                    "muted-dark": "#737373", // Labels, captions (~4.6:1 on black)
                },
            },
            fontFamily: {
                sans: ["Inter", "system-ui", "sans-serif"],
            },
        },
    },
};
