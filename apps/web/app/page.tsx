"use client";

import Image from "next/image";
import Link from "next/link";

import { LanguageSwitch } from "@/components/language-switch";
import { useI18n } from "@/lib/i18n";

const copy = {
  en: {
    eyebrow: "AI-native analysis workspace",
    headline: "Bitlysis helps people understand analysis.",
    subhead:
      "Upload data, paste a website, bring a document, or ask a question. Bitlysis turns analytical output into plain-language insight, evidence, and next steps.",
    cta: "Start understanding your analysis",
    secondary: "See how it works",
    promise: "An AI companion helping humans understand analysis.",
    flows: [
      "Analyze a spreadsheet",
      "Understand a document",
      "Review a website",
      "Explain survey results",
    ],
    workflowTitle: "From source to understanding",
    workflow: [
      "Upload or ask",
      "AI reads the source",
      "Explanation appears first",
      "Evidence supports every insight",
      "Next steps stay human-readable",
    ],
    useCasesTitle: "Built for calm interpretation",
    useCases: [
      ["Students", "Decode statistics without feeling lost."],
      ["Researchers", "Trace summaries back to supporting evidence."],
      ["Educators", "Turn complex material into teachable explanations."],
      ["Small teams", "Read business data without a BI learning curve."],
    ],
  },
  vi: {
    eyebrow: "Không gian phân tích AI-native",
    headline: "Bitlysis giúp con người hiểu phân tích.",
    subhead:
      "Tải dữ liệu, dán website, đưa tài liệu hoặc đặt câu hỏi. Bitlysis chuyển kết quả phân tích thành insight dễ hiểu, có bằng chứng và bước tiếp theo.",
    cta: "Bắt đầu hiểu phân tích của bạn",
    secondary: "Xem cách hoạt động",
    promise: "Một AI đồng hành giúp con người hiểu phân tích.",
    flows: [
      "Phân tích bảng tính",
      "Hiểu tài liệu",
      "Đọc website",
      "Giải thích khảo sát",
    ],
    workflowTitle: "Từ nguồn dữ liệu đến hiểu biết",
    workflow: [
      "Tải lên hoặc hỏi",
      "AI đọc nguồn",
      "Giải thích xuất hiện trước",
      "Insight luôn có bằng chứng",
      "Bước tiếp theo dễ hành động",
    ],
    useCasesTitle: "Thiết kế để diễn giải nhẹ nhàng",
    useCases: [
      ["Sinh viên", "Hiểu thống kê mà không bị choáng."],
      ["Nhà nghiên cứu", "Lần ngược tóm tắt về bằng chứng hỗ trợ."],
      ["Giảng viên", "Biến nội dung phức tạp thành giải thích dễ dạy."],
      ["Đội nhóm nhỏ", "Đọc dữ liệu kinh doanh mà không cần học BI."],
    ],
  },
} as const;

export default function Home() {
  const { locale } = useI18n();
  const c = copy[locale];

  return (
    <main className="min-h-screen overflow-hidden bg-[#f6f0e6] text-[#161615]">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(#ded6c7_1px,transparent_1px),linear-gradient(90deg,#ded6c7_1px,transparent_1px)] bg-[size:52px_52px] opacity-55" />
      <div className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 sm:px-6 lg:px-10">
        <header className="flex min-h-20 items-center justify-between border-b border-[#161615] py-4">
          <Link href="/" className="flex items-center gap-3" aria-label="Bitlysis home">
            <span className="flex h-10 w-10 items-center justify-center border border-[#161615] bg-[#161615] text-lg font-black text-[#f6f0e6]">
              B
            </span>
            <span className="text-2xl font-black uppercase leading-none tracking-[0.02em] sm:text-3xl">
              Bitlysis
            </span>
          </Link>
          <LanguageSwitch />
        </header>

        <section className="grid flex-1 gap-8 border-b border-[#161615] py-10 lg:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)] lg:py-14">
          <div className="flex flex-col justify-between gap-10">
            <div>
              <p className="w-fit border border-[#161615] bg-[#dff2e8] px-3 py-1 text-xs font-black uppercase tracking-[0.22em]">
                {c.eyebrow}
              </p>
              <h1 className="mt-6 max-w-5xl text-[clamp(3rem,10vw,8.4rem)] font-black uppercase leading-[1.04] tracking-normal">
                {c.headline}
              </h1>
              <p className="mt-7 max-w-2xl text-lg leading-relaxed text-[#3d3932] sm:text-xl">
                {c.subhead}
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/workspace"
                  className="inline-flex min-h-12 items-center justify-center border border-[#161615] bg-[#161615] px-5 py-3 text-sm font-black uppercase tracking-[0.12em] text-[#f6f0e6] shadow-[6px_6px_0_#a8d8bd] transition hover:translate-x-0.5 hover:translate-y-0.5 hover:shadow-[4px_4px_0_#a8d8bd]"
                >
                  {c.cta}
                </Link>
                <a
                  href="#workflow"
                  className="inline-flex min-h-12 items-center justify-center border border-[#161615] bg-[#f6f0e6] px-5 py-3 text-sm font-black uppercase tracking-[0.12em] text-[#161615]"
                >
                  {c.secondary}
                </a>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              {c.flows.map((flow, index) => (
                <div
                  key={flow}
                  className="border border-[#161615] bg-[#fffaf0] p-4 text-sm font-bold uppercase tracking-[0.08em]"
                >
                  <span className="mr-3 text-[#0f766e]">0{index + 1}</span>
                  {flow}
                </div>
              ))}
            </div>
          </div>

          <div className="relative min-h-[520px] border border-[#161615] bg-[#fffaf0] p-4 shadow-[10px_10px_0_#161615] lg:min-h-0">
            <div className="absolute left-4 top-4 z-10 max-w-60 border border-[#161615] bg-[#f6f0e6] p-3 text-sm font-semibold leading-snug">
              {c.promise}
            </div>
            <Image
              src="/svg/mascot-researching.svg"
              alt=""
              width={560}
              height={560}
              priority
              className="absolute bottom-0 right-0 h-[82%] w-[82%] object-contain object-bottom opacity-95"
            />
            <Image
              src="/svg/robot-smiling.svg"
              alt=""
              width={180}
              height={180}
              className="absolute bottom-6 left-4 hidden h-36 w-36 object-contain opacity-90 sm:block"
            />
          </div>
        </section>

        <section id="workflow" className="grid gap-8 border-b border-[#161615] py-10 lg:grid-cols-[0.68fr_1fr]">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-[#0f766e]">Workflow</p>
            <h2 className="mt-3 text-4xl font-black uppercase leading-[1.08] sm:text-5xl">
              {c.workflowTitle}
            </h2>
          </div>
          <div className="grid gap-3">
            {c.workflow.map((item, index) => (
              <div key={item} className="grid grid-cols-[64px_1fr] border border-[#161615] bg-[#fffaf0]">
                <div className="flex items-center justify-center border-r border-[#161615] bg-[#dff2e8] text-xl font-black">
                  {index + 1}
                </div>
                <div className="p-4 text-lg font-bold">{item}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-6 py-10 lg:grid-cols-[1fr_1.2fr]">
          <div className="relative min-h-80 overflow-hidden border border-[#161615] bg-[#161615] text-[#f6f0e6]">
            <Image
              src="/svg/mascot-talking.svg"
              alt=""
              width={420}
              height={420}
              className="absolute bottom-0 right-0 h-full w-full object-contain object-bottom opacity-80"
            />
            <p className="relative z-10 max-w-xs p-5 text-2xl font-black uppercase leading-[1.1]">
              {c.useCasesTitle}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {c.useCases.map(([title, description]) => (
              <div key={title} className="border border-[#161615] bg-[#fffaf0] p-5">
                <h3 className="text-xl font-black uppercase">{title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-[#514b42]">{description}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
