import { useState, useEffect } from 'react';
import { Folder, File, ChevronRight, ChevronLeft, Link as LinkIcon, X } from 'lucide-react';

interface TorBoxBrowserProps {
    onSelect: (path: string) => void;
    onClose: () => void;
    apiBase: string;
}

export default function TorBoxBrowser({ onSelect, onClose, apiBase }: TorBoxBrowserProps) {
    const [path, setPath] = useState("/");
    const [items, setItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        setLoading(true);
        fetch(`${apiBase}/torbox/list?path=${encodeURIComponent(path)}`)
            .then(r => r.json())
            .then(d => {
                setItems(d.items || []);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, [path, apiBase]);

    const navigateTo = (item: any) => {
        if (item.is_dir) {
            setPath(item.path);
        }
    };

    const goBack = () => {
        if (path === "/") return;
        const parts = path.split("/").filter(Boolean);
        parts.pop();
        setPath("/" + (parts.join("/") ? parts.join("/") : ""));
    };

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in duration-300">
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-2xl flex flex-col max-h-[80vh] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="p-4 border-b border-zinc-800 bg-zinc-800/50 flex justify-between items-center">
                    <div>
                        <h3 className="text-zinc-100 font-bold flex items-center gap-2">
                            <Folder className="w-4 h-4 text-amber-500" />
                            Explorador de TorBox
                        </h3>
                        <p className="text-[10px] text-zinc-500 font-mono mt-0.5 truncate max-w-md">{path}</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-zinc-700 rounded-full transition-colors">
                        <X className="w-5 h-5 text-zinc-400" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2">
                    {path !== "/" && path !== "" && (
                        <div
                            onClick={goBack}
                            className="flex items-center gap-3 p-3 cursor-pointer hover:bg-zinc-800/50 rounded-lg text-zinc-400 group transition-all"
                        >
                            <ChevronLeft className="w-5 h-5 group-hover:-translate-x-1 duration-200" />
                            <span className="text-sm">... (Volver)</span>
                        </div>
                    )}

                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-20 gap-4">
                            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500"></div>
                            <span className="text-xs text-zinc-500 font-medium">Leyendo montaje de TorBox...</span>
                        </div>
                    ) : items.length === 0 ? (
                        <div className="text-center py-20 text-zinc-600 italic">Este directorio está vacío.</div>
                    ) : (
                        <div className="grid gap-1 px-1">
                            {items.map((item, idx) => (
                                <div
                                    key={idx}
                                    className={`flex items-center justify-between p-3 rounded-xl border border-transparent hover:bg-zinc-800 hover:border-zinc-700 transition-all group cursor-pointer`}
                                    onClick={() => item.is_dir ? navigateTo(item) : null}
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        {item.is_dir ? (
                                            <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
                                                <Folder className="w-5 h-5 text-amber-500 shrink-0" />
                                            </div>
                                        ) : (
                                            <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                                                <File className="w-5 h-5 text-blue-400 shrink-0" />
                                            </div>
                                        )}
                                        <span className={`text-sm truncate ${item.is_dir ? 'text-zinc-200 font-bold' : 'text-zinc-400 font-medium'}`}>
                                            {item.name}
                                        </span>
                                    </div>

                                    {!item.is_dir ? (
                                        <button
                                            onClick={(e) => { e.stopPropagation(); onSelect(item.path); }}
                                            className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded-lg text-xs flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all scale-95 group-hover:scale-100 shadow-xl"
                                        >
                                            <LinkIcon className="w-3.5 h-3.5" />
                                            Vincular
                                        </button>
                                    ) : (
                                        <ChevronRight className="w-4 h-4 text-zinc-700 group-hover:translate-x-1 group-hover:text-zinc-400 duration-200" />
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="p-4 bg-zinc-950/50 border-t border-zinc-800 text-[10px] text-zinc-600 flex justify-between">
                    <span>TorBox Rclone Mount (/mnt/torbox)</span>
                    <span>Selecciona un archivo de video para vincularlo manualmente</span>
                </div>
            </div>
        </div>
    );
}
