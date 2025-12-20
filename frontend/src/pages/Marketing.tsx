import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import rocketBoy from '../assets/rocket-boy.png';

// --- Assets & Icons ---

const Logo = () => (
    <div className="flex items-center gap-2 font-bold text-2xl tracking-tight text-[#3D405B]">
        <div className="h-10 w-10 bg-[#E07A5F] rounded-lg rotate-3 flex items-center justify-center shadow-lg border-2 border-[#3D405B]">
            <svg className="w-6 h-6 text-[#FAF9F6]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
        </div>
        PaperDrop
    </div>
);

const HeartIcon = () => (
    <svg className="w-6 h-6 text-[#E07A5F] fill-current" viewBox="0 0 24 24">
        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
    </svg>
);

const CreateIcon = () => (
    <svg className="w-16 h-16 text-[#E07A5F]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 19l7-7 3 3-7 7-3-3z" />
        <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
        <path d="M2 2l5 5" />
        <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
);

const SendIcon = () => (
    <svg className="w-16 h-16 text-[#3D405B]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 2L11 13" />
        <path d="M22 2l-7 20-4-9-9-4 20-7z" />
        <path d="M18 6l-3 3" className="opacity-50" />
        <path d="M20 4l-2 2" className="opacity-30" />
    </svg>
);

const PrintIcon = () => (
    <svg className="w-16 h-16 text-[#E07A5F]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="10" width="18" height="10" rx="2" />
        <path d="M7 10V4a2 2 0 012-2h6a2 2 0 012 2v6" />
        <path d="M7 20v2h10v-2" />
        <path d="M12 14v2" />
        <path d="M12 6h.01" />
        <path d="M10 14h4" className="opacity-50" />
    </svg>
);

// --- Components ---

const TornPaperDivider = ({ flip = false, color = "bg-[#FAF9F6]" }: { flip?: boolean; color?: string }) => (
    <div className={`absolute left-0 w-full overflow-hidden leading-[0] ${flip ? 'bottom-0 rotate-180' : 'top-0'}`}>
        <svg className={`relative block w-[calc(100%+1.3px)] h-[50px] ${color}`} data-name="Layer 1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 120" preserveAspectRatio="none">
            <path d="M321.39,56.44c58-10.79,114.16-30.13,172-41.86,82.39-16.72,168.19-17.73,250.45-.39C823.78,31,906.67,72,985.66,92.83c70.05,18.48,146.53,26.09,214.34,3V0H0V27.35A600.21,600.21,0,0,0,321.39,56.44Z" className="fill-current"></path>
        </svg>
    </div>
);

// Stop Motion Animation Component
const StopMotionFloat = ({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) => (
    <div
        className="animate-float-stepped"
        style={{ animationDelay: `${delay}ms` }}
    >
        {children}
    </div>
);

// --- Main Page ---

export function Marketing() {
    const { user } = useAuth();

    useEffect(() => {
        const script = document.createElement('script');
        script.src = "https://player.vimeo.com/api/player.js";
        script.async = true;
        document.body.appendChild(script);
        return () => {
            document.body.removeChild(script);
        }
    }, []);

    return (
        <div className="min-h-screen bg-[#FAF9F6] text-[#3D405B] font-sans selection:bg-[#E07A5F] selection:text-white overflow-x-hidden">
            <style>{`
            @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;800&family=Gloria+Hallelujah&display=swap');
            
            body { font-family: 'Nunito', sans-serif; }
            .font-hand { font-family: 'Gloria Hallelujah', cursive; }
            
            /* Stop Motion Feel: Jerky animation steps */
            @keyframes float-stepped {
                0% { transform: translateY(0px) rotate(1deg); }
                25% { transform: translateY(-8px) rotate(-1deg); }
                50% { transform: translateY(0px) rotate(1deg); }
                75% { transform: translateY(4px) rotate(-2deg); }
                100% { transform: translateY(0px) rotate(1deg); }
            }
            .animate-float-stepped {
                animation: float-stepped 4s steps(6) infinite;
            }

            @keyframes print-receipt {
                0% { height: 0px; opacity: 0; }
                100% { height: 160px; opacity: 1; }
            }
            .animate-print {
                animation: print-receipt 3s steps(20) forwards;
                animation-delay: 1s;
            }

            /* Texture Overlay */
            .paper-texture {
                background-image: url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.05'/%3E%3C/svg%3E");
                pointer-events: none;
            }
        `}</style>

            <div className="fixed inset-0 paper-texture z-50 mix-blend-multiply" />

            {/* --- Navbar --- */}
            <nav className="relative z-40 px-6 py-6 max-w-5xl mx-auto flex items-center justify-between">
                <Logo />
                <div className="flex gap-4">
                    {user ? (
                        <Link to="/dashboard" className="px-6 py-2 rounded-full bg-[#3D405B] text-[#FAF9F6] font-bold shadow-[4px_4px_0px_0px_#E07A5F] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#E07A5F] transition-all border-2 border-[#3D405B]">
                            Dashboard
                        </Link>
                    ) : (
                        <>
                            <Link to="/login" className="hidden sm:block px-5 py-2 rounded-full font-bold text-[#3D405B] hover:bg-[#3D405B]/5 transition border-2 border-transparent">
                                Log in
                            </Link>
                            <Link to="/register" className="px-6 py-2 rounded-full bg-[#E07A5F] text-[#FAF9F6] font-bold shadow-[4px_4px_0px_0px_#3D405B] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#3D405B] transition-all border-2 border-[#3D405B]">
                                Get Started
                            </Link>
                        </>
                    )}
                </div>
            </nav>

            {/* --- Hero Section --- */}
            <header className="relative pt-12 pb-32 overflow-hidden">
                <div className="max-w-5xl mx-auto px-6 grid md:grid-cols-2 gap-12 items-center">

                    {/* Text Content */}
                    <div className="relative z-10 order-2 md:order-1">
                        <div className="inline-block bg-[#F2CC8F] px-4 py-1 rounded-full border-2 border-[#3D405B] shadow-[2px_2px_0px_0px_#3D405B] rotate-[-2deg] mb-6">
                            <span className="font-bold text-sm uppercase tracking-wider">New Arrival</span>
                        </div>
                        <h1 className="text-5xl md:text-6xl font-extrabold leading-[1.1] mb-6 text-[#3D405B]">
                            Messages you can <span className="text-[#E07A5F] underline decoration-wavy decoration-4 underline-offset-4">hold</span>.
                        </h1>
                        <p className="text-xl md:text-2xl text-[#3D405B]/80 mb-8 font-medium">
                            Don't just send a text. Drop a note. <br className="hidden md:block" />
                            The thermal printer for love notes, drawings, and daily smiles.
                        </p>
                        <div className="flex flex-col sm:flex-row gap-4">
                            <Link to={user ? "/dashboard" : "/register"} className="px-8 py-4 rounded-xl bg-[#3D405B] text-[#FAF9F6] text-lg font-bold shadow-[6px_6px_0px_0px_#E07A5F] hover:translate-y-[2px] hover:shadow-[4px_4px_0px_0px_#E07A5F] transition-all border-2 border-[#3D405B] text-center">
                                {user ? "Go to Dashboard" : "Get Your PaperDrop"}
                            </Link>
                            <p className="text-sm font-hand text-[#3D405B]/60 self-center rotate-2">
                                * No ink needed. Ever!
                            </p>
                        </div>
                    </div>

                    {/* Hero Animation / Visual */}
                    <div className="relative z-10 order-1 md:order-2 flex justify-center">
                        <StopMotionFloat>
                            <div className="relative">
                                {/* The Printer Device */}
                                <div className="w-64 h-64 bg-white rounded-3xl border-4 border-[#3D405B] shadow-[12px_12px_0px_0px_rgba(61,64,91,0.2)] relative z-20 flex flex-col items-center justify-center">
                                    {/* Face/Eyes */}
                                    <div className="flex gap-8 mb-4">
                                        <div className="w-4 h-4 rounded-full bg-[#3D405B] animate-pulse"></div>
                                        <div className="w-4 h-4 rounded-full bg-[#3D405B] animate-pulse"></div>
                                    </div>
                                    {/* Mouth/Slot */}
                                    <div className="w-32 h-2 bg-[#3D405B]/10 rounded-full mb-2"></div>

                                    {/* Printed Paper Animation */}
                                    <div className="absolute top-[60%] left-1/2 -translate-x-1/2 w-40 bg-[#FAF9F6] border-2 border-[#3D405B] border-dashed border-t-0 shadow-sm z-10 overflow-hidden animate-print origin-top flex flex-col items-center p-2">
                                        <div className="w-full h-full flex flex-col items-center justify-center font-hand text-center leading-tight">
                                            <HeartIcon />
                                            <span className="mt-2 block">Love you!</span>
                                            <span className="text-xs text-gray-400 mt-1">- Dad</span>
                                        </div>
                                        {/* Jagged Bottom Edge */}
                                        <div className="absolute bottom-0 w-full h-2 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMiA0IiBwcmVzZXJ2ZUFzcGVjdHJhdGlvPSJub25lIj48cGF0aCBkPSJNMCAwdjRjMi0zIDQtMyA2IDBzNC0zIDYgMFYweiIgZmlsbD0iI2ZmZiIvPjwvc3ZnPg==')] bg-repeat-x bg-bottom"></div>
                                    </div>
                                </div>

                                {/* Decorative Elements around printer */}
                                <div className="absolute -top-6 -right-6 w-16 h-16 bg-[#F2CC8F] rounded-full border-2 border-[#3D405B] z-0"></div>
                                <div className="absolute -bottom-4 -left-8 w-24 h-24 bg-[#E07A5F] rounded-full border-2 border-[#3D405B] z-0 opacity-50"></div>
                            </div>
                        </StopMotionFloat>
                    </div>
                </div>
            </header>

            {/* --- The Problem Section (Darker contrast) --- */}
            <section className="bg-[#3D405B] text-[#FAF9F6] py-24 relative">
                <TornPaperDivider color="fill-[#FAF9F6]" />

                <div className="max-w-4xl mx-auto px-6 text-center relative z-10">
                    <StopMotionFloat delay={500}>
                        <h2 className="text-3xl md:text-4xl font-bold mb-8 font-hand -rotate-1">
                            "Digital messages vanish in a second."
                        </h2>
                    </StopMotionFloat>
                    <div className="grid md:grid-cols-3 gap-8 mt-12">
                        <div className="bg-[#FAF9F6] text-[#3D405B] p-6 rounded-2xl -rotate-2 border-2 border-dashed border-[#3D405B]/30 opacity-80">
                            <div className="text-4xl mb-4">📱</div>
                            <p className="font-bold">Buried in feeds</p>
                            <p className="text-sm mt-2">Screenshots get lost. Texts get scrolled past.</p>
                        </div>
                        <div className="bg-[#FAF9F6] text-[#3D405B] p-6 rounded-2xl rotate-1 border-2 border-dashed border-[#3D405B]/30 opacity-80">
                            <div className="text-4xl mb-4">💨</div>
                            <div className="font-bold">Zero Texture</div>
                            <p className="text-sm mt-2">You can't hold a pixel. It lacks feeling.</p>
                        </div>
                        <div className="bg-[#FAF9F6] text-[#3D405B] p-6 rounded-2xl -rotate-1 border-2 border-dashed border-[#3D405B]/30 opacity-80">
                            <div className="text-4xl mb-4">😶</div>
                            <div className="font-bold">Impersonal</div>
                            <p className="text-sm mt-2">Just another notification in a sea of noise.</p>
                        </div>
                    </div>
                </div>

                {/* Bottom Transition */}
                <div className="absolute bottom-0 w-full overflow-hidden leading-[0] rotate-180">
                    <svg className="relative block w-[calc(100%+1.3px)] h-[50px] fill-[#E07A5F]" data-name="Layer 1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 120" preserveAspectRatio="none">
                        <path d="M321.39,56.44c58-10.79,114.16-30.13,172-41.86,82.39-16.72,168.19-17.73,250.45-.39C823.78,31,906.67,72,985.66,92.83c70.05,18.48,146.53,26.09,214.34,3V0H0V27.35A600.21,600.21,0,0,0,321.39,56.44Z"></path>
                    </svg>
                </div>
            </section>

            {/* --- Emotional Connection Section (Coral) --- */}
            <section className="bg-[#E07A5F] py-24 relative">
                <div className="max-w-5xl mx-auto px-6 grid md:grid-cols-2 gap-12 items-center">
                    <div className="order-2 md:order-1 relative">
                        {/* Placeholder for Video/Stop Motion Montage */}
                        <div className="bg-[#FAF9F6] p-4 rounded-lg shadow-xl -rotate-2 border-4 border-[#3D405B] max-w-[320px] mx-auto">
                            <div className="relative overflow-hidden rounded border-2 border-[#3D405B] border-dashed" style={{ padding: '177.77% 0 0 0' }}>
                                <iframe
                                    src="https://player.vimeo.com/video/1148263510?h=85ee9b918f&badge=0&autopause=0&player_id=0&app_id=58479"
                                    frameBorder="0"
                                    allow="autoplay; fullscreen; picture-in-picture; clipboard-write; encrypted-media; web-share"
                                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
                                    title="Paper_drop_48s_202512201138_pvyai"
                                ></iframe>
                            </div>
                        </div>
                        {/* Paper scraps */}
                        <div className="absolute -bottom-6 -left-6 bg-white p-3 shadow-md rotate-6 border border-[#3D405B]/20">
                            <p className="font-hand text-xs">Good luck today!</p>
                        </div>
                    </div>

                    <div className="order-1 md:order-2 text-[#FAF9F6]">
                        <h3 className="text-3xl font-extrabold mb-6">Something real to carry in their pocket.</h3>
                        <p className="text-lg font-medium opacity-90 mb-6">
                            Whether it's a doodle from Dad, a grocery list from Mom, or a surprise love note.
                            PaperDrop prints it instantly at home.
                        </p>
                        <ul className="space-y-4 font-bold text-lg">
                            <li className="flex items-center gap-3">
                                <span className="bg-[#F2CC8F] text-[#3D405B] p-1 rounded">🌿</span> No Ink Required (Thermal)
                            </li>
                            <li className="flex items-center gap-3">
                                <span className="bg-[#F2CC8F] text-[#3D405B] p-1 rounded">🏠</span> Prints Instantly over Wi-Fi
                            </li>
                            <li className="flex items-center gap-3">
                                <span className="bg-[#F2CC8F] text-[#3D405B] p-1 rounded">✂️</span> Satisfying Tear-off Edge
                            </li>
                        </ul>
                    </div>
                </div>

                <TornPaperDivider flip color="fill-[#FAF9F6]" />
            </section>

            {/* --- How it Works / App --- */}
            <section className="py-24 bg-[#FAF9F6]">
                <div className="max-w-6xl mx-auto px-6">
                    <div className="text-center mb-16">
                        <span className="font-hand text-[#E07A5F] text-xl font-bold -rotate-2 inline-block">So easy, it feels like magic</span>
                        <h2 className="text-4xl font-extrabold text-[#3D405B] mt-2">From your phone to their hands.</h2>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8">
                        {/* Step 1 */}
                        <div className="relative group">
                            <div className="bg-white rounded-3xl p-8 border-4 border-[#3D405B] shadow-[8px_8px_0px_0px_#3D405B] transition-transform group-hover:-translate-y-2">
                                <div className="h-40 bg-[#E07A5F]/10 rounded-2xl mb-6 flex items-center justify-center border-2 border-dashed border-[#E07A5F]">
                                    <CreateIcon />
                                </div>
                                <h3 className="text-xl font-bold text-[#3D405B] mb-2">1. Create</h3>
                                <p className="text-[#3D405B]/70">Draw a doodle, snap a photo, or type a quick note in the PaperDrop app.</p>
                            </div>
                        </div>

                        {/* Step 2 */}
                        <div className="relative group mt-8 md:mt-0">
                            {/* Arrow for desktop */}
                            <div className="hidden md:block absolute top-1/2 -left-6 w-8 h-8 text-[#3D405B] z-10">➝</div>

                            <div className="bg-white rounded-3xl p-8 border-4 border-[#3D405B] shadow-[8px_8px_0px_0px_#F2CC8F] transition-transform group-hover:-translate-y-2">
                                <div className="h-40 bg-[#F2CC8F]/10 rounded-2xl mb-6 flex items-center justify-center border-2 border-dashed border-[#F2CC8F]">
                                    <SendIcon />
                                </div>
                                <h3 className="text-xl font-bold text-[#3D405B] mb-2">2. Send</h3>
                                <p className="text-[#3D405B]/70">Hit send from anywhere. The office, the train, or the other room.</p>
                            </div>
                        </div>

                        {/* Step 3 */}
                        <div className="relative group mt-16 md:mt-0">
                            {/* Arrow for desktop */}
                            <div className="hidden md:block absolute top-1/2 -left-6 w-8 h-8 text-[#3D405B] z-10">➝</div>

                            <div className="bg-white rounded-3xl p-8 border-4 border-[#3D405B] shadow-[8px_8px_0px_0px_#E07A5F] transition-transform group-hover:-translate-y-2">
                                <div className="h-40 bg-[#E07A5F]/10 rounded-2xl mb-6 flex items-center justify-center border-2 border-dashed border-[#E07A5F]">
                                    <PrintIcon />
                                </div>
                                <h3 className="text-xl font-bold text-[#3D405B] mb-2">3. Print</h3>
                                <p className="text-[#3D405B]/70">The PaperDrop lights up and prints your message instantly. Zzzt!</p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* --- Testimonials / Wall of Love --- */}
            <section className="py-24 bg-[#F2CC8F]/20 relative overflow-hidden">
                <div className="max-w-5xl mx-auto px-6 relative z-10">
                    <h2 className="text-3xl font-extrabold text-[#3D405B] text-center mb-12">Fridge doors love us.</h2>

                    <div className="columns-1 md:columns-2 lg:columns-3 gap-6 space-y-6">
                        {/* Note 1 */}
                        <div className="break-inside-avoid bg-white p-6 shadow-md rotate-1 border border-[#3D405B]/10 relative">
                            <div className="w-4 h-4 rounded-full bg-red-400 absolute -top-2 left-1/2 -translate-x-1/2 border border-red-600 shadow-sm"></div>
                            <p className="font-hand text-lg mb-2">"Dad, don't forget the milk! 🥛"</p>
                            <p className="text-xs text-gray-400 font-sans uppercase tracking-wide text-right">- Printed 2m ago</p>
                        </div>

                        {/* Note 2 */}
                        <div className="break-inside-avoid bg-white p-4 shadow-md -rotate-2 border-t-8 border-[#E07A5F] border-x border-b border-gray-100">
                            <div className="aspect-square bg-gray-100 mb-2 rounded border border-dashed border-gray-300 flex items-center justify-center overflow-hidden">
                                <img src={rocketBoy} alt="Boy on a rocket" className="w-full h-full object-contain p-2" />
                            </div>
                            <p className="font-hand text-sm text-center">To infinity!</p>
                        </div>

                        {/* Note 3 */}
                        <div className="break-inside-avoid bg-[#FFF9C4] p-6 shadow-md rotate-3 border border-yellow-400/30">
                            <div className="w-24 h-6 bg-black/10 absolute -top-3 left-1/2 -translate-x-1/2 rotate-1 skew-x-12 opacity-20"></div> {/* Tape look */}
                            <div className="w-24 h-6 bg-[#FFFFFF]/40 absolute -top-3 left-1/2 -translate-x-1/2 rotate-1 skew-x-12 backdrop-blur-sm"></div> {/* Tape look */}
                            <p className="font-sans text-sm font-bold mb-2">Shopping List:</p>
                            <ul className="list-disc pl-4 font-hand text-sm">
                                <li>Eggs</li>
                                <li>Bread</li>
                                <li>Coffee beans (Important!)</li>
                            </ul>
                        </div>

                        {/* Review */}
                        <div className="break-inside-avoid bg-[#3D405B] text-[#FAF9F6] p-6 rounded-xl shadow-xl">
                            <p className="font-medium italic mb-4">"My daughter actually checks this instead of her phone. It's become our little ritual when I'm traveling."</p>
                            <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-full bg-[#E07A5F]"></div>
                                <span className="text-sm font-bold">Mark T.</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* --- Footer CTA --- */}
            <section className="bg-[#3D405B] text-[#FAF9F6] py-24 text-center relative overflow-hidden">
                {/* Background Pattern */}
                <div className="absolute inset-0 opacity-5" style={{ backgroundImage: 'radial-gradient(#FAF9F6 2px, transparent 2px)', backgroundSize: '30px 30px' }}></div>

                <div className="max-w-3xl mx-auto px-6 relative z-10">
                    <StopMotionFloat>
                        <div className="inline-block mb-6">
                            <Logo />
                        </div>
                    </StopMotionFloat>
                    <h2 className="text-4xl md:text-5xl font-extrabold mb-8">Make their day.</h2>
                    <p className="text-xl mb-10 text-[#FAF9F6]/80">
                        Get the PaperDrop Starter Kit. Includes printer, 3 rolls of thermal paper, and the app.
                    </p>
                    <div className="flex flex-col sm:flex-row justify-center gap-4 items-center">
                        <Link to={user ? "/dashboard" : "/register"} className="px-8 py-4 rounded-full bg-[#E07A5F] text-white text-lg font-bold shadow-[0px_0px_20px_rgba(224,122,95,0.4)] hover:scale-105 transition-transform border-2 border-white/20">
                            {user ? "Go to Dashboard" : "Buy Now - $89"}
                        </Link>
                        <span className="text-sm opacity-60">Ships free in the US</span>
                    </div>
                </div>
            </section>

            <footer className="bg-[#3D405B] border-t border-[#FAF9F6]/10 py-12 text-center text-[#FAF9F6]/40 text-sm">
                <p>&copy; 2024 PaperDrop. Hand-coded with ❤️.</p>
            </footer>
        </div>
    );
}
