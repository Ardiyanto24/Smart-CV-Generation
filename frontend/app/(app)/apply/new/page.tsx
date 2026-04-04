// cv-agent/frontend/app/(app)/apply/new/page.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

// ── Types ─────────────────────────────────────────────────────────────────────
type Step = 1 | 2;

interface Step1Values {
  company_name: string;
  position: string;
}

interface Step2Values {
  jd_raw: string;
  jr_raw: string;
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function NewApplicationPage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>(1);
  const [applicationId, setApplicationId] = useState<string | null>(null);

  // Step 1 state
  const [step1, setStep1] = useState<Step1Values>({
    company_name: "",
    position: "",
  });
  const [step1Loading, setStep1Loading] = useState(false);
  const [step1Error, setStep1Error] = useState<string | null>(null);

  // Step 2 state
  const [step2, setStep2] = useState<Step2Values>({
    jd_raw: "",
    jr_raw: "",
  });
  const [step2Loading, setStep2Loading] = useState(false);
  const [step2Error, setStep2Error] = useState<string | null>(null);

  // ── Step 1: Create application ──────────────────────────────────────────────
  async function handleContinue(e: React.FormEvent) {
    e.preventDefault();
    setStep1Error(null);

    if (!step1.company_name.trim()) {
      setStep1Error("Company name is required.");
      return;
    }
    if (!step1.position.trim()) {
      setStep1Error("Position is required.");
      return;
    }

    setStep1Loading(true);
    try {
      const response = await apiFetch("/applications", {
        method: "POST",
        body: JSON.stringify({
          company_name: step1.company_name.trim(),
          position: step1.position.trim(),
        }),
      });

      // Simpan application_id untuk dipakai di Step 2
      setApplicationId(response.id);
      setStep(2);
    } catch (err) {
      setStep1Error(
        err instanceof Error
          ? err.message
          : "Failed to create application. Please try again."
      );
    } finally {
      setStep1Loading(false);
    }
  }

  // ── Step 2: Start workflow ──────────────────────────────────────────────────
  async function handleStartAnalysis(e: React.FormEvent) {
    e.preventDefault();
    setStep2Error(null);

    if (!step2.jd_raw.trim()) {
      setStep2Error("Job Description is required.");
      return;
    }
    if (!step2.jr_raw.trim()) {
      setStep2Error("Job Requirements is required.");
      return;
    }
    if (!applicationId) {
      setStep2Error("Application ID is missing. Please go back and try again.");
      return;
    }

    setStep2Loading(true);
    try {
      // Trigger workflow — response akan berisi status: "interrupted"
      // saat Cluster 2 selesai dan workflow pause di interrupt pertama
      await apiFetch(`/applications/${applicationId}/start`, {
        method: "POST",
        body: JSON.stringify({
          jd_raw: step2.jd_raw.trim(),
          jr_raw: step2.jr_raw.trim(),
        }),
      });

      // Navigasi segera ke /gap — WorkflowProgress di sana akan
      // menampilkan progress via SSE sementara agent berjalan
      router.push(`/apply/${applicationId}/gap`);
    } catch (err) {
      setStep2Error(
        err instanceof Error
          ? err.message
          : "Failed to start analysis. Please try again."
      );
      setStep2Loading(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-8 max-w-2xl mx-auto">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">
          New Application
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Tell us about the role you are applying for
        </p>
      </div>

      {/* Step Indicator */}
      <div className="flex items-center gap-3">
        <StepIndicator number={1} label="Application Details" active={step === 1} done={step > 1} />
        <div className="flex-1 h-px bg-gray-200" />
        <StepIndicator number={2} label="Job Description" active={step === 2} done={false} />
      </div>

      {/* ── Step 1 ── */}
      {step === 1 && (
        <Card>
          <form onSubmit={handleContinue} className="flex flex-col gap-5">
            <div>
              <h2 className="text-base font-semibold text-gray-900">
                Application Details
              </h2>
              <p className="mt-0.5 text-sm text-gray-500">
                Enter the company and position you are applying for
              </p>
            </div>

            <Input
              label="Company Name"
              placeholder="e.g. PT Maju Bersama"
              value={step1.company_name}
              onChange={(e) =>
                setStep1({ ...step1, company_name: e.target.value })
              }
            />

            <Input
              label="Position"
              placeholder="e.g. Data Analyst"
              value={step1.position}
              onChange={(e) =>
                setStep1({ ...step1, position: e.target.value })
              }
            />

            {step1Error && (
              <p className="text-sm text-red-600">{step1Error}</p>
            )}

            <div className="flex justify-end pt-1">
              <Button type="submit" loading={step1Loading}>
                Continue
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* ── Step 2 ── */}
      {step === 2 && (
        <Card>
          <form onSubmit={handleStartAnalysis} className="flex flex-col gap-5">
            <div>
              <h2 className="text-base font-semibold text-gray-900">
                Job Description & Requirements
              </h2>
              <p className="mt-0.5 text-sm text-gray-500">
                Paste the full job description and requirements from the job posting
              </p>
            </div>

            <Textarea
              label="Job Description (JD)"
              placeholder="Paste the job description here — responsibilities, day-to-day tasks, expectations..."
              value={step2.jd_raw}
              onChange={(e) =>
                setStep2({ ...step2, jd_raw: e.target.value })
              }
              rows={10}
            />

            <Textarea
              label="Job Requirements (JR)"
              placeholder="Paste the job requirements here — qualifications, skills, experience needed..."
              value={step2.jr_raw}
              onChange={(e) =>
                setStep2({ ...step2, jr_raw: e.target.value })
              }
              rows={10}
            />

            {step2Error && (
              <p className="text-sm text-red-600">{step2Error}</p>
            )}

            <div className="flex items-center justify-between pt-1">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                ← Back
              </button>
              <Button type="submit" loading={step2Loading}>
                Start Analysis
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}

// ── Step Indicator Sub-component ──────────────────────────────────────────────
function StepIndicator({
  number,
  label,
  active,
  done,
}: {
  number: number;
  label: string;
  active: boolean;
  done: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
          done
            ? "bg-blue-600 text-white"
            : active
            ? "bg-blue-600 text-white"
            : "bg-gray-200 text-gray-500"
        }`}
      >
        {done ? "✓" : number}
      </div>
      <span
        className={`text-sm font-medium ${
          active ? "text-gray-900" : "text-gray-400"
        }`}
      >
        {label}
      </span>
    </div>
  );
}