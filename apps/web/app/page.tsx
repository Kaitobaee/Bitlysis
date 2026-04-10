import Link from "next/link";

import { HeroLottie } from "@/components/hero-lottie";

export default function Home() {
  return (
    <main className="h-screen overflow-hidden bg-[radial-gradient(circle_at_18%_22%,#f0eefe_0%,#f7f7fb_42%,#ffffff_100%)] text-[#47435f]">
      <div className="mx-auto flex h-full w-full max-w-7xl flex-col px-4 md:px-10">
        <header className="flex h-22 shrink-0 items-center justify-between md:h-24">
          <Link href="/" className="inline-flex items-center gap-3 text-[#6f56e9]">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#6f56e9] text-lg font-black text-white">
              B
            </span>
            <span className="text-[36px] font-black tracking-tight md:text-[38px]">bitlysis</span>
          </Link>

          <button
            type="button"
            className="rounded-full border border-[#e2def6] bg-white px-5 py-2 text-xs font-bold uppercase tracking-[0.08em] text-[#8a86a2] transition hover:border-[#d4cdee]"
          >
            Ngôn ngữ hiển thị: Tiếng Việt
          </button>
        </header>

        <section className="grid flex-1 items-center gap-8 pb-10 md:grid-cols-[1fr_1fr] md:gap-14 md:pb-14">
          <div className="relative flex items-center justify-center">
            <div className="pointer-events-none absolute h-110 w-110 rounded-full bg-[radial-gradient(circle,#ece6ff_0%,#f7f7fb_72%)] blur-xl md:h-130 md:w-130" />
            <div className="relative">
              <HeroLottie />
            </div>
          </div>

          <div className="relative z-10 flex items-center justify-center">
            <div className="w-full max-w-xl text-center">
              <p className="text-label text-[#8f80c7]">Bitlysis workspace</p>
              <h1 className="mt-4 font-serif text-[42px] font-semibold leading-[1.14] tracking-[-0.01em] text-[#47435f] md:text-[56px]">
                Học phân tích dữ liệu miễn phí, nhanh gọn và hiệu quả!
              </h1>

              <p className="mx-auto mt-5 max-w-lg text-[17px] leading-relaxed text-[#78738e] md:text-[22px]">
                Tải file, chạy phân tích và xem kết quả trực quan trong một quy trình đơn giản.
              </p>

              <div className="mt-9 space-y-4">
                <Link
                  href="/workspace"
                  className="block rounded-2xl bg-[#6f56e9] px-6 py-4 text-center text-lg font-bold uppercase tracking-[0.04em] text-white shadow-[0_6px_0_#5b46c4] transition hover:translate-y-px hover:bg-[#674fe0] hover:shadow-[0_5px_0_#5b46c4]"
                >
                  Bắt đầu
                </Link>
                <Link
                  href="/workspace"
                  className="block rounded-2xl border-2 border-[#ddd9f0] bg-white px-6 py-4 text-center text-lg font-bold uppercase tracking-[0.04em] text-[#6f56e9] transition hover:border-[#cec8e8]"
                >
                  Tôi đã có tài khoản
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
