// Minimal ambient typing for the Google Identity Services (GIS) global, scoped to exactly what
// components/GoogleSignInButton.tsx uses - no @types package exists for this, and pulling in a
// full SDK (e.g. @react-oauth/google) just for typing isn't worth a new dependency here.
export {};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(config: {
            client_id: string;
            callback: (response: { credential: string; select_by?: string }) => void;
            use_fedcm_for_button?: boolean;
            itp_support?: boolean;
          }): void;
          renderButton(
            parent: HTMLElement,
            options: {
              type?: "standard" | "icon";
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              text?: "signin_with" | "signup_with" | "continue_with" | "signin";
              shape?: "rectangular" | "pill" | "circle" | "square";
              width?: number;
              logo_alignment?: "left" | "center";
            }
          ): void;
        };
      };
    };
  }
}
