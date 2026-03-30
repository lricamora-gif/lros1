<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LROS v60.3 • Transparent Sovereign</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#010204] text-slate-400 p-8 font-mono">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-10 border-b border-slate-900 pb-8">
            <h1 class="text-2xl font-black italic text-white uppercase tracking-tighter">LROS <span class="text-blue-500">Sovereign</span></h1>
            <div class="text-[9px] bg-green-900/10 text-green-500 px-4 py-1 rounded-full border border-green-500/20 font-bold uppercase tracking-widest">
                CONSTITUTIONAL INTEGRITY: 100%
            </div>
        </header>

        <div class="mb-10 bg-slate-900/20 border border-slate-800/50 rounded-full p-1">
            <div id="progBar" class="bg-blue-600 h-2 rounded-full transition-all duration-1000" style="width: 0%"></div>
            <p class="text-[8px] text-center mt-2 uppercase tracking-[0.4em] text-blue-500 font-bold">Neural Learning Progress: <span id="progText">0</span>%</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10 text-center">
            <div class="bg-slate-900/30 p-8 rounded-[40px] border border-slate-800/50">
                <p class="text-[9px] text-slate-600 mb-2 uppercase tracking-widest">Active Agent Pulse</p>
                <h2 id="activeAgent" class="text-5xl font-bold text-white italic">000</h2>
            </div>
            <div class="bg-slate-900/30 p-8 rounded-[40px] border border-slate-800/50">
                <p class="text-[9px] text-slate-600 mb-2 uppercase tracking-widest">Success DNA</p>
                <h2 id="successCount" class="text-5xl font-bold text-green-500 italic">0</h2>
            </div>
            <div class="bg-slate-900/30 p-8 rounded-[40px] border border-slate-800/50">
                <p class="text-[9px] text-slate-600 mb-2 uppercase tracking-widest">Next Evolution</p>
                <h2 id="nextEvolve" class="text-3xl font-bold text-blue-400 italic pt-2">00:00:00</h2>
            </div>
            <div class="bg-blue-600/10 p-8 rounded-[40px] border border-blue-600/30">
                <p id="physStatus" class="text-[9px] text-blue-500 mb-2 uppercase font-bold tracking-widest">Bacoor Warehouse</p>
                <h2 class="text-2xl font-bold text-white uppercase pt-1">SECURED</h2>
            </div>
        </div>

        <div class="bg-black border border-slate-900 rounded-[50px] p-10 shadow-2xl">
            <div id="logs" class="h-80 overflow-y-auto space-y-2 text-[10px] scrollbar-hide">
                > Calibrating Sovereign Transparency...
            </div>
        </div>
    </div>

    <script>
        const API = "https://lros1.onrender.com";

        async function sync() {
            try {
                const res = await fetch(`${API}/api/orchestrate/status`);
                const data = await res.json();
                
                document.getElementById('progBar').style.width = data.learning_perc + '%';
                document.getElementById('progText').innerText = data.learning_perc;
                document.getElementById('activeAgent').innerText = data.active_agent.toString().padStart(3, '0');
                document.getElementById('successCount').innerText = data.successes.toLocaleString();
                document.getElementById('nextEvolve').innerText = data.next_evolve;
                
                document.getElementById('logs').innerHTML = data.logs.map(l => {
                    const style = l.includes('SUCCESS') ? 'text-green-400 font-bold border-l-2 border-green-500 pl-2' : 'text-slate-800';
                    const highlighted = l.replace(/(AGENT-\d+)/, '<span class="text-white font-black">$1</span>');
                    return `<div class="py-1 border-b border-white/5 ${style}">> ${highlighted}</div>`;
                }).reverse().join('');
            } catch (e) { }
        }
        setInterval(sync, 1500);
    </script>
</body>
</html>
