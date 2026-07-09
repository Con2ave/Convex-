import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeftIcon, ChevronRightIcon, MailIcon } from "../components/icons";

const SUPPORT_EMAIL = "rolandtenkoko@gmail.com";

const FAQ_ITEMS = [
  {
    question: "How do I earn Knowledge Points?",
    answer:
      "Start a study session and keep it running. Knowledge Points are awarded when you end a verified session, based on how many 30-minute blocks you actually studied, plus small bonuses for a perfect session and your first session of the day.",
  },
  {
    question: "What's the streak multiplier?",
    answer:
      "Studying on consecutive days multiplies the points you earn, up to 2.5x at a 60-day streak. Miss a day and the streak resets, so consistency pays off more than one long session.",
  },
  {
    question: "Do I need to subscribe to study?",
    answer:
      "No. Studying and earning Knowledge Points is always free. A subscription only unlocks cashing your points out for Mobile Money.",
  },
  {
    question: "How do I redeem points for cash?",
    answer:
      "From your Profile, tap Redeem, choose a fixed GHS tier, and pick the mobile network for the number you want the money sent to. You'll need an active subscription to do this.",
  },
  {
    question: "How is my study time verified?",
    answer:
      "The app checks in on you occasionally during a session with quick attention or recall prompts. Answer them within the time window and your session stays verified; miss too many and it gets flagged and won't earn points.",
  },
  {
    question: "Which networks can I redeem to?",
    answer: "MTN, Telecel, and AirtelTigo are all supported for Mobile Money redemptions.",
  },
];

export function FAQ() {
  const navigate = useNavigate();
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="app-shell">
      <div className="app-column">
        <div className="topbar" style={{ marginBottom: "0.6rem" }}>
          <button className="topbar-icon-btn" aria-label="Back" onClick={() => navigate(-1)}>
            <ChevronLeftIcon size={18} />
          </button>
        </div>

        <h1 className="display-heading" style={{ fontSize: "1.7rem", marginBottom: "0.4rem" }}>
          FAQ
        </h1>
        <p className="text-soft" style={{ fontSize: "0.85rem", marginBottom: "1.4rem" }}>
          Common questions about studying, points, and redemptions.
        </p>

        <div className="card" style={{ marginBottom: "1.4rem", padding: "0.3rem 1.1rem" }}>
          {FAQ_ITEMS.map((item, i) => {
            const isOpen = openIndex === i;
            return (
              <div key={item.question} style={{ borderTop: i === 0 ? "none" : "1px solid var(--border)" }}>
                <button
                  type="button"
                  onClick={() => setOpenIndex(isOpen ? null : i)}
                  style={{
                    width: "100%",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "0.8rem",
                    padding: "0.9rem 0",
                    background: "none",
                    border: "none",
                    textAlign: "left",
                    font: "inherit",
                    color: "inherit",
                    cursor: "pointer",
                  }}
                >
                  <span style={{ fontWeight: 700, fontSize: "0.9rem" }}>{item.question}</span>
                  <ChevronRightIcon
                    size={16}
                    style={{
                      flex: "none",
                      transform: isOpen ? "rotate(90deg)" : "none",
                      transition: "transform 0.15s ease",
                      color: "var(--text-soft)",
                    }}
                  />
                </button>
                {isOpen && (
                  <p className="text-soft" style={{ fontSize: "0.85rem", margin: "0 0 1rem", lineHeight: 1.5 }}>
                    {item.answer}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        <p className="stat-label" style={{ marginBottom: "0.6rem" }}>Still have a question?</p>
        <a href={`mailto:${SUPPORT_EMAIL}?subject=ConVex%20question`} className="list-row" style={{ marginBottom: "1.2rem" }}>
          <span className="icon-tile" style={{ width: 44, height: 44 }}>
            <MailIcon size={20} />
          </span>
          <span className="list-row-main">
            <div className="list-row-title">Email the developer</div>
            <div className="list-row-sub">{SUPPORT_EMAIL}</div>
          </span>
        </a>
      </div>
    </div>
  );
}
