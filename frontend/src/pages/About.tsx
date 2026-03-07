/**
 * pages/About.tsx
 * ---------------
 * Portfolio showcase page for GitHub Code Explainer.
 * Sections: Hero → How It Works → Tech Stack → Features → Developer → CTA
 */

import { Link } from "react-router-dom";
import {
  SiReact, SiTypescript, SiPython,
  SiFastapi, SiLangchain,
} from "react-icons/si";
import {
  FiGithub, FiLinkedin, FiZap, FiSearch,
  FiCode, FiLayers,
} from "react-icons/fi";
import { HiOutlineChip } from "react-icons/hi";
import { VscDatabase } from "react-icons/vsc";
import { AiOutlineInstagram } from "react-icons/ai";

// ── Data ─────────────────────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  { icon: <FiGithub size={22} />,     label: "GitHub URL",           desc: "Paste any public repo link"          },
  { icon: <FiCode   size={22} />,     label: "Download & Chunk",     desc: "Files split into semantic blocks"    },
  { icon: <HiOutlineChip size={22} />,label: "BGE Embeddings",       desc: "BAAI model encodes each chunk"       },
  { icon: <VscDatabase size={22} />,  label: "FAISS Index",          desc: "Lightning-fast vector search"        },
  { icon: <FiSearch size={22} />,     label: "RAG Retrieval",        desc: "Top-K chunks fetched per question"   },
  { icon: <FiZap    size={22} />,     label: "Groq LLM Answer",      desc: "Response generated in milliseconds"  },
];

const TECH_STACK = [
  { icon: <SiReact      size={28} color="#61dafb" />, name: "React",      note: "Frontend UI"         },
  { icon: <SiTypescript size={28} color="#3178c6" />, name: "TypeScript", note: "Type-safe client"    },
  { icon: <SiPython     size={28} color="#3572A5" />, name: "Python",     note: "Backend language"    },
  { icon: <SiFastapi    size={28} color="#009688" />, name: "FastAPI",    note: "REST API layer"       },
  { icon: <VscDatabase  size={28} color="#f5a623" />, name: "FAISS",      note: "Vector search"       },
  { icon: <HiOutlineChip size={28} color="#a78bfa"/>, name: "BGE Model",  note: "Embeddings"          },
  { icon: <SiLangchain  size={28} color="#1c3c3c" />, name: "LangChain",  note: "RAG orchestration"   },
];

const FEATURES = [
  { icon: <FiSearch size={16} />,      text: "Ask in plain English — no grep, no cloning. Get accurate answers with exact source file references"  },
  { icon: <FiZap    size={16} />,      text: "Any public GitHub repo indexed in under 60 seconds. No setup, no config, no API keys to manage"        },
  { icon: <FiLayers size={16} />,      text: "Answers come with citations — see exactly which files and chunks the AI used to form its response"      },
  { icon: <FiCode   size={16} />,      text: "Ask about file structure and it consults every indexed file — not just a handful of search results"     },
  { icon: <VscDatabase size={16} />,   text: "Works across any language — Python, JavaScript, Go, Rust, Java and more, all indexed the same way"       },
  { icon: <HiOutlineChip size={16} />, text: "Cross-file reasoning — the AI synthesizes knowledge across hundreds of files to give complete answers"   },
];

// ── Developer info — UPDATE THESE ────────────────────────────────────────────
const DEV = {
  name:     "Guduri Shashikanth",
  title:    "Developer · AI Enthusiast",
  bio:      "I build intelligent applications that bridge modern AI capabilities with practical developer tooling. This project combines RAG pipelines, vector search, and LLM APIs into a tool I genuinely wanted to exist.",
  github:   "https://github.com/GuduriShashikanth",
  linkedin: "https://www.linkedin.com/in/guduri-shashikanth/",
  instagram: "https://www.instagram.com/shashi.iiii_/", // update this
  skills: [
    "Python", "JavaScript", "React.js", "Node.js",
    "Flask", "Express.js", "TensorFlow", "MongoDB", "PostgreSQL",
    "AWS (Lambda · S3 · DynamoDB · CloudFormation)", "Deep Learning", "NLP",
    "RAG", "LangChain",
  ],
};
// ─────────────────────────────────────────────────────────────────────────────

export default function About() {
  return (
    <div className="about-page">

      {/* ── 1. HERO ── */}
      <section className="about-hero">
        <div className="about-hero-inner">
          <div className="about-hero-badge">Open Source · Portfolio Project</div>
          <h1 className="about-hero-title">
            GitHub Code Explainer
          </h1>
          <p className="about-hero-subtitle">
            Paste any GitHub repository. Ask anything in plain English.<br />
            Get precise, context-aware answers.
          </p>
          <div className="about-hero-actions">
            <Link to="/" className="about-btn-primary">
              <FiZap size={15} /> Try the App
            </Link>
            <a
              href={DEV.github + "/githubcodeexplainer"}
              target="_blank"
              rel="noreferrer"
              className="about-btn-secondary"
            >
              <FiGithub size={15} /> View on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* ── 2. PROBLEM / SOLUTION ── */}
      <section className="about-section">
        <div className="about-container">
          <div className="about-two-col">
            <div className="about-problem-card">
              <h3>The Problem</h3>
              <p>
                Reading an unfamiliar codebase takes hours. You have to clone it,
                grep through hundreds of files, trace call stacks, and guess at
                architecture — just to answer a simple question.
              </p>
            </div>
            <div className="about-solution-card">
              <h3>The Solution</h3>
              <p>
                Paste a GitHub URL. The app downloads, chunks, and indexes the
                entire codebase in under 60 seconds. Then ask in plain English —
                "how does auth work?" or "what does the parser do?" — and get a
                precise answer with source citations.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 3. HOW IT WORKS ── */}
      <section className="about-section about-section--dark">
        <div className="about-container">
          <h2 className="about-section-title">How It Works</h2>
          <p className="about-section-sub">A 6-step RAG pipeline, end to end</p>
          <div className="about-pipeline">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.label} className="about-pipeline-step">
                <div className="about-pipeline-icon">{step.icon}</div>
                <div className="about-pipeline-label">{step.label}</div>
                <div className="about-pipeline-desc">{step.desc}</div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className="about-pipeline-arrow">→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 4. TECH STACK ── */}
      <section className="about-section">
        <div className="about-container">
          <h2 className="about-section-title">Tech Stack</h2>
          <div className="about-tech-grid">
            {TECH_STACK.map((t) => (
              <div key={t.name} className="about-tech-card">
                {t.icon}
                <span className="about-tech-name">{t.name}</span>
                <span className="about-tech-note">{t.note}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 5. FEATURES ── */}
      <section className="about-section about-section--dark">
        <div className="about-container">
          <h2 className="about-section-title">Features</h2>
          <div className="about-features-grid">
            {FEATURES.map((f) => (
              <div key={f.text} className="about-feature-row">
                <span className="about-feature-icon">{f.icon}</span>
                <span>{f.text}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 6. DEVELOPER ── */}
      <section className="about-section about-section--dark">
        <div className="about-container">
          <h2 className="about-section-title">About the Developer</h2>

          <div className="about-dev-editorial">
            {/* Top row: avatar + identity */}
            <div className="about-dev-top">
              <div className="about-dev-avatar">{DEV.name.charAt(0)}</div>
              <div>
                <h3 className="about-dev-name">{DEV.name}</h3>
                <p className="about-dev-title">{DEV.title}</p>
                <div className="about-dev-links">
                  <a href={DEV.github}   target="_blank" rel="noreferrer" className="about-social-link">
                    <FiGithub size={14} /> GitHub
                  </a>
                  <a href={DEV.linkedin} target="_blank" rel="noreferrer" className="about-social-link">
                    <FiLinkedin size={14} /> LinkedIn
                  </a>
                  <a href={DEV.instagram} target="_blank" rel="noreferrer" className="about-social-link">
                    <AiOutlineInstagram size={15} /> Instagram
                  </a>
                </div>
              </div>
            </div>

            {/* Bio */}
            <p className="about-dev-bio">{DEV.bio}</p>

            {/* Skills */}
            <p className="about-dev-skills-label">My skills include</p>
            <div className="about-dev-skills">
              {DEV.skills.map((s) => (
                <span key={s} className="about-dev-skill">{s}</span>
              ))}
            </div>
          </div>

        </div>
      </section>

      {/* ── 7. CTA ── */}
      <section className="about-cta">
        <div className="about-container">
          <h2>Ready to explore a codebase?</h2>
          <p>Paste any public GitHub URL and start asking questions in seconds.</p>
          <Link to="/" className="about-btn-primary about-btn-primary--lg">
            <FiZap size={16} /> Try the App →
          </Link>
        </div>
      </section>

    </div>
  );
}
