<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LROS v62.2 • Sovereign Command</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #010101; color: #94a3b8; font-family: 'Inter', sans-serif; }
        .gold-glow { box-shadow: 0 0 30px rgba(212, 175, 55, 0.1); border: 1px solid rgba(212, 175, 55, 0.2); }
        .glass { background: rgba(10, 10, 12, 0.9); backdrop-filter: blur(15px); }
        .gold-text { color: #d4af37; }
        .scrollbar-hide::-webkit-scrollbar { display: none; }
    </style>
</head>
<body class="p-8">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-10 border-b border-white/5 pb-10">
            <div>
                <p class="text-[10px] gold-text font-bold uppercase tracking-[0.6em] mb-2">Universal Intelligence Swarm</p>
                <h1 class="text-4xl text-white font-extralight italic tracking-tighter">LROS Eternal</h1>
            </div>
            <button onclick="manualArchive()" class="bg-[#d4af37]/5 border border-[#d4af37]/30 px-10 py-3 rounded-full text-[10px] gold-text font-bold uppercase tracking-widest hover:bg-[#d4af37] hover:text-black transition duration-700">
                Anchor Eternal DNA ⤓
            </button>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
            <div class="glass p-8 rounded-[40px] border border-white/5 relative overflow-hidden">
                <p class="text-[9px] uppercase tracking-widest text-white/40 mb-2">Neural Learning</p>
                <h3 class="text-4xl text-white font-light"><span id="progText">99.1</span><span class="text-xs gold-text">%</span></h3>
                <div class="absolute bottom-0 left-0 h-1 bg-[#d4af37] transition-all duration-700" id="progBar" style="width: 99%"></div>
            </div>
            <div class="glass p-8 rounded-[40px] border border-white/5 text-center">
                <p class="text-[9px] uppercase tracking-widest text-white/40 mb-2">Active Agent</p>
                <h3 id="activeAgent" class="text-4xl text-white font-mono">000</h3>
            </div>
            <div class="glass p-8 rounded-[40px] border border-white/5 text-center">
                <p class="text-[9px] uppercase tracking-widest text-white/40 mb-2">Success Tally</p>
                <h3 id="successCount" class="text-4xl gold-text font-bold italic">1500</h3>
            </div>
            <div class="glass p-8 rounded-[40px] border border-white/5 text-center">
                <p class="text-[9px] uppercase tracking-widest text-white/40 mb-2">Mutation Uses</p>
                <h3 id="useCount" class="text-4xl text-white/20 font-light italic">7500</h3>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div class="lg:col-span-2 glass rounded-[50px] p-12 gold-glow">
                <h4 class="text-[11px] gold-text font-bold uppercase tracking-[0.5em] mb-10">Eternal Audit Ledger</h4>
                <div id="ledgerCards" class="space-y-4">
                    <div class="text-white/10 italic text-xs">Awaiting Mutation Synchronization...</div>
                </div>
            </div>
            <div class="glass rounded-[50px] p-12 border border-white/5">
                <h4 class="text-[11px] text-white uppercase tracking-[0.5em] mb-10">Intelligence Stream</h4>
                <div id="logs" class="h-[400px] overflow-y-auto space-y-4 text-[10px] font-light scrollbar-hide"></div>
            </div>
        </div>
    </div>

    <script>
        const API = "https://lros1.onrender.com";

        async function manualArchive() {
            try {
                const res = await fetch(`${API}/api/manual-archive`, { method: 'POST' });
                if (res.ok) alert("Eternal Intelligence Anchored to Google Doc.");
            } catch (e) { alert("Archive Failed: Check Connection."); }
        }

        async function sync() {
            try {
                const res = await fetch(`${API}/api/orchestrate/status`);
                const data = await res.json();
                
                document.getElementById('progBar').style.width = data.learning_perc + '%';
                document.getElementById('progText').innerText = data.learning_perc;
                document.getElementById('activeAgent').innerText = data.active_agent.toString().padStart(3, '0');
                document.getElementById('successCount').innerText = data.successes.toLocaleString();
                document.getElementById('useCount').innerText = data.uses.toLocaleString();

                document.getElementById('ledgerCards').innerHTML = data.mutation_ledger.map(m => `
                    <div class="bg-white/[0.02] p-6 rounded-3xl border border-white/[0.05] flex justify-between items-center transition hover:bg-white/5">
                        <div class="flex gap-8 items-center">
                            <span class="font-mono gold-text text-xs font-bold">${m.version}</span>
                            <div>
                                <p class="text-[10px] text-white font-bold uppercase tracking-[0.2em]">${m.domain}</p>
                                <p class="text-[8px] text-white/30 mt-1">Agent-${m.agent} | TS: ${m.ts}</p>
                            </div>
                        </div>
                        <div class="text-right">
                            <p class="text-[10px] text-white font-mono font-bold">${m.score}</p>
                            <p class="text-[7px] text-green-500 uppercase font-black tracking-widest">Verified</p>
                        </div>
                    </div>`).reverse().join('');

                document.getElementById('logs').innerHTML = data.logs.map(l => 
                    `<div class="py-2 border-b border-white/5 text-white/30 tracking-tight">▹ ${l}</div>`
                ).reverse().join('');
            } catch (e) { }
        }
        setInterval(sync, 1000); // 1-second pulse for real-time movement
    </script>
</body>
</html>
