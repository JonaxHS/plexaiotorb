// @ts-nocheck
import React, { useState, useEffect, useRef } from 'react';
import { Search, Film, Tv, Play, Pause, Plus, TerminalSquare, X, Settings, Activity, CheckCircle2, XCircle, Trash2, Link as LinkIcon, Zap, Download, FileText } from 'lucide-react';
import TorBoxBrowser from './components/TorBoxBrowser';

// Si accedes desde otro equipo en tu red (ej. iPad), usa la IP local en vez de localhost.
// Detectamos el host dinámicamente:
const HOST = window.location.hostname === 'localhost' ? 'localhost' : window.location.hostname;
const API_BASE = `http://${HOST}:8000/api`;

function LibraryItemCard({ item, mediaType, onClick }: any) {
    const [details, setDetails] = useState<any>(null);
    useEffect(() => {
        if (item.tmdb_id) {
            fetch(`${API_BASE}/details/${mediaType}/${item.tmdb_id}`)
                .then(r => r.json())
                .then(d => setDetails(d))
                .catch(() => { });
        }
    }, [item.tmdb_id, mediaType]);

    return (
        <div onClick={() => onClick(item, mediaType)} className="group relative flex flex-col gap-2 cursor-pointer">
            <div className="relative aspect-[2/3] rounded-lg overflow-hidden bg-zinc-800 border border-zinc-700/50 transition-transform duration-300 group-hover:scale-105 group-hover:ring-2 group-hover:ring-amber-500/50 shadow-lg">
                {details?.poster_path ? (
                    <img src={details.poster_path} alt={item.name} className="w-full h-full object-cover" />
                ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-zinc-600 p-2 text-center text-xs">
                        <CheckCircle2 className="w-8 h-8 text-zinc-700 mb-2" />
                        <span className="line-clamp-3">{item.name}</span>
                    </div>
                )}
                <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/80 to-transparent">
                    <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center border border-green-500/50">
                        <CheckCircle2 className="w-3 h-3 text-green-500" />
                    </div>
                </div>
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                    <TerminalSquare className="w-8 h-8 text-white" />
                    <span className="text-white text-xs font-semibold">Ver Estructura</span>
                </div>
            </div>
            <div>
                <h3 className="font-medium text-zinc-100 line-clamp-1 group-hover:text-amber-400 transition-colors text-sm" title={item.name}>
                    {details?.title || details?.name || item.name}
                </h3>
            </div>
        </div>
    );
}

export default function App() {
    const [setupMode, setSetupMode] = useState(true); // default true until check
    const [checkingStatus, setCheckingStatus] = useState(true);

    // Setup Form State
    const [setupData, setSetupData] = useState({
        tmdb_api_key: "",
        aiostreams_url: "http://localhost:XXXX",
        torbox_email: "",
        torbox_password: "",
        plex_server_name: "PlexAioTorb"
    });
    const [setupStep, setSetupStep] = useState(1);
    const [setupMessage, setSetupMessage] = useState("");

    const [query, setQuery] = useState("");
    const [results, setResults] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    const [selectedItem, setSelectedItem] = useState<any>(null);
    const [showDetails, setShowDetails] = useState(false);
    const [mediaDetails, setMediaDetails] = useState<any>(null);
    const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
    const [episodes, setEpisodes] = useState<any[]>([]);
    const [symlinkExists, setSymlinkExists] = useState(false);

    const [streams, setStreams] = useState<any[]>([]);
    const [loadingStreams, setLoadingStreams] = useState(false);

    // -- New Library State --
    const [activeTab, setActiveTab] = useState<'search' | 'library'>('search');
    const [libraryData, setLibraryData] = useState<{ movies: any[], shows: any[] }>({ movies: [], shows: [] });
    const [loadingLibrary, setLoadingLibrary] = useState(false);

    const [showLibStruct, setShowLibStruct] = useState(false);
    const [libStructData, setLibStructData] = useState<any[]>([]);
    const [libStructItem, setLibStructItem] = useState<{ name: string, media_type: string, tmdb_id: number } | null>(null);
    const [libStructDetails, setLibStructDetails] = useState<any>(null);
    const [loadingStruct, setLoadingStruct] = useState(false);
    const [symlinkStatuses, setSymlinkStatuses] = useState<Record<string, 'testing' | 'alive' | 'dead'>>({});
    const [selectedSymlinkInfo, setSelectedSymlinkInfo] = useState<any>(null);

    const [logs, setLogs] = useState<string[]>(["[System] Conectado a PlexAioTorb GUI."]);
    const [globalLogs, setGlobalLogs] = useState<string[]>([]);
    const [rcloneStatus, setRcloneStatus] = useState<string>("checking");
    const [showSettings, setShowSettings] = useState(false);
    const [notifications, setNotifications] = useState<string[]>([]);
    const [activeDownloads, setActiveDownloads] = useState<Record<string, any>>({});
    const [showTorBoxBrowser, setShowTorBoxBrowser] = useState(false);
    const [browsingJob, setBrowsingJob] = useState<any>(null);
    const [activeLogTab, setActiveLogTab] = useState<'backend' | 'rclone' | 'local'>('backend');
    const logsEndRef = useRef<HTMLDivElement>(null);
    const [jobLogs, setJobLogs] = useState<Record<string, string[]>>({});    // Per-job logs
    const [expandedJobLog, setExpandedJobLog] = useState<string | null>(null); // Currently expanded job
    const jobLogSinceRef = useRef<Record<string, number>>({});               // Cursor per job
    const jobLogsEndRef = useRef<HTMLDivElement>(null);
    const [streamCacheStatuses, setStreamCacheStatuses] = useState<Record<string, boolean>>({}); // Cache status per stream URL

    // -- Live Settings State --
    const [settingsForm, setSettingsForm] = useState({ tmdb_api_key: '', aiostreams_url: '' });
    const [settingsSaving, setSettingsSaving] = useState(false);

    // -- Discovery State --
    const [trendingMedia, setTrendingMedia] = useState<any[]>([]);
    const [genres, setGenres] = useState<any[]>([]);
    const [selectedGenre, setSelectedGenre] = useState<number | null>(null);
    const [discoveryLoading, setDiscoveryLoading] = useState(false);
    const [discoveryType, setDiscoveryType] = useState<'movie' | 'tv'>('movie');
    const [currentPage, setCurrentPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const observerTarget = useRef<HTMLDivElement>(null);

    // -- UX Optimization State --
    const [episodeSyncStatus, setEpisodeSyncStatus] = useState<Record<number, 'synced' | 'pending' | 'none'>>({});
    const searchTimeout = useRef<any>(null);
    const [downloadingStreamId, setDownloadingStreamId] = useState<string | null>(null);
    const [globalNotification, setGlobalNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

    // -- Actor Details State --
    const [selectedPerson, setSelectedPerson] = useState<any>(null);
    const [personCredits, setPersonCredits] = useState<any[]>([]);
    const [personDetailsLoading, setPersonDetailsLoading] = useState(false);

    // Check initial setup status
    React.useEffect(() => {
        fetch(`${API_BASE}/status`)
            .then(r => r.json())
            .then(d => {
                if (d.configured) setSetupMode(false);
                setCheckingStatus(false);
            })
            .catch((e) => {
                console.error("Backend offline", e);
                setCheckingStatus(false);
            });
    }, []);

    // Global Logs and Status Poller
    useEffect(() => {
        if (setupMode || checkingStatus) return;
        const interval = setInterval(() => {
            fetch(`${API_BASE}/logs`)
                .then(r => r.json()).then(d => {
                    if (d.logs) setGlobalLogs(d.logs);
                }).catch(() => { });

            fetch(`${API_BASE}/rclone/status`)
                .then(r => r.json())
                .then(d => {
                    setRcloneStatus(d.status);
                }).catch(() => setRcloneStatus("disconnected"));

            // Polling de notificaciones
            fetch(`${API_BASE}/notifications`)
                .then(r => r.json())
                .then(d => {
                    if (d.messages && d.messages.length > 0) {
                        setNotifications(prev => [...prev, ...d.messages]);
                        setTimeout(() => {
                            setNotifications(prev => prev.slice(d.messages.length));
                        }, 5000);
                    }
                }).catch(() => { });

            // Polling de descargas activas
            fetch(`${API_BASE}/downloads/active`)
                .then(r => r.json())
                .then(d => {
                    setActiveDownloads(d);
                }).catch(() => { });
        }, 5000);
        return () => clearInterval(interval);
    }, [setupMode, checkingStatus]);

    // Polling de logs por trabajo — en un efecto separado para evitar stale closure
    useEffect(() => {
        if (setupMode || checkingStatus) return;
        const jobLogInterval = setInterval(() => {
            Object.entries(activeDownloads).forEach(([id, job]: [string, any]) => {
                if (job.status === 'Completed' || job.status === 'Error' || job.status === 'Cancelled') return;
                const since = jobLogSinceRef.current[id] || 0;
                fetch(`${API_BASE}/jobs/${id}/logs?since=${since}`)
                    .then(r => r.json())
                    .then(d => {
                        if (d.logs && d.logs.length > 0) {
                            setJobLogs(prev => ({ ...prev, [id]: [...(prev[id] || []), ...d.logs] }));
                            jobLogSinceRef.current[id] = d.total;
                        }
                    }).catch(() => { });
            });
        }, 3000); // Poll más rápido (3s) para logs en tiempo real
        return () => clearInterval(jobLogInterval);
    }, [setupMode, checkingStatus, activeDownloads]);


    const fetchTrending = async () => {
        try {
            const res = await fetch(`${API_BASE}/tmdb/trending?media_type=all&time_window=week`);
            const data = await res.json();
            setTrendingMedia(data.results || []);
        } catch (err) { }
    };

    const fetchGenres = async (type: 'movie' | 'tv') => {
        try {
            const res = await fetch(`${API_BASE}/tmdb/genres?media_type=${type}`);
            const data = await res.json();
            setGenres(data.genres || []);
        } catch (err) { }
    };

    const fetchDiscovery = async (type: 'movie' | 'tv', genreId: number | null, page: number = 1, append: boolean = false, isSearchContext: boolean = false) => {
        // Prevent generic discovery updates from overriding active search results,
        // unless this *is* a search request being deliberately fired.
        if (query && !isSearchContext && page === 1) return;

        if (page === 1) setDiscoveryLoading(true);
        try {
            let url = '';

            // If there's an active query, we ALWAYS use the search endpoint.
            // (isSearchContext just allowed us to bypass the block on page=1).
            if (query) {
                url = `${API_BASE}/search?q=${encodeURIComponent(query)}&page=${page}`;
            } else if (genreId) {
                url = `${API_BASE}/tmdb/discover?media_type=${type}&genre_id=${genreId}&page=${page}`;
            } else {
                url = `${API_BASE}/tmdb/trending?media_type=${type}&time_window=week&page=${page}`;
            }

            const res = await fetch(url);
            const data = await res.json();

            const newResults = data.results || [];
            if (append) {
                setResults(prev => [...prev, ...newResults]);
            } else {
                setResults(newResults);
            }

            setHasMore(page < (data.total_pages || 1));
            setCurrentPage(page);
        } catch (err) { }
        finally { if (page === 1) setDiscoveryLoading(false); }
    };

    useEffect(() => {
        if (!setupMode && !checkingStatus) {
            fetchTrending();
        }
    }, [setupMode, checkingStatus]);

    useEffect(() => {
        if (!setupMode && !checkingStatus) {
            fetchGenres(discoveryType);
            setCurrentPage(1);
            fetchDiscovery(discoveryType, selectedGenre, 1, false, false);
        }
    }, [setupMode, checkingStatus, discoveryType, selectedGenre]);

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [globalLogs]);



    // Real-time Search Debounce
    useEffect(() => {
        if (!query) {
            if (activeTab === 'search') {
                setCurrentPage(1);
                fetchDiscovery(discoveryType, selectedGenre, 1, false, false);
            }
            return;
        }

        if (searchTimeout.current) clearTimeout(searchTimeout.current);
        searchTimeout.current = setTimeout(() => {
            setCurrentPage(1);
            fetchDiscovery(discoveryType, selectedGenre, 1, false, true);
            setActiveTab('search');
            addLog(`Buscando en TMDB: "${query}"`);
        }, 500);

        return () => clearTimeout(searchTimeout.current);
    }, [query]);

    // Intersection Observer for Infinite Scroll
    useEffect(() => {
        const observer = new IntersectionObserver(
            entries => {
                if (entries[0].isIntersecting && hasMore && !discoveryLoading && !selectedItem && !selectedPerson) {
                    fetchDiscovery(discoveryType, selectedGenre, currentPage + 1, true, !!query);
                }
            },
            { threshold: 0.1, rootMargin: '400px' }
        );

        const currentTarget = observerTarget.current;
        if (currentTarget) {
            observer.observe(currentTarget);
        }

        // Cleanup on unmount
        return () => {
            if (currentTarget) observer.unobserve(currentTarget);
            observer.disconnect();
            document.body.classList.remove('overflow-hidden');
        };
    }, [hasMore, discoveryLoading, currentPage, discoveryType, selectedGenre, query, selectedItem, selectedPerson]);

    // Fetch Live Settings when Modal Opens
    useEffect(() => {
        if (showSettings && !setupMode) {
            fetch(`${API_BASE}/settings`)
                .then(r => r.json())
                .then(d => {
                    setSettingsForm({ tmdb_api_key: d.tmdb_api_key || '', aiostreams_url: d.aiostreams_url || '' });
                }).catch(e => console.error(e));
        }
    }, [showSettings, setupMode]);

    const handleSaveSettings = async () => {
        setSettingsSaving(true);
        try {
            const res = await fetch(`${API_BASE}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settingsForm)
            });
            if (res.ok) {
                setGlobalNotification({ message: 'Ajustes guardados en vivo correctamente', type: 'success' });
                setShowSettings(false);
            } else {
                setGlobalNotification({ message: 'Error al verificar ajustes (HTTP)', type: 'error' });
            }
        } catch (e) {
            console.error(e);
            setGlobalNotification({ message: 'Fallo al contactar el API de Ajustes', type: 'error' });
        } finally {
            setSettingsSaving(false);
        }
    };

    const addLog = (msg: string) => {
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
    };

    const handleSetupSubmit = async () => {
        setSetupMessage("Configurando servicios... (10s)");
        try {
            const res = await fetch(`${API_BASE}/setup`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(setupData)
            });
            if (res.ok) {
                setSetupMessage("¡Configuración lista! Recargando en 5 segundos...");
                setTimeout(() => {
                    window.location.reload();
                }, 5000);
            } else {
                setSetupMessage("Error al guardar la configuración.");
            }
        } catch (err) {
            setSetupMessage(`Error de conexión: ${err}`);
        }
    };

    const handleManualLink = async (path: string) => {
        if (!browsingJob) return;
        addLog(`Intentando vincular manualmente: ${path}`);
        try {
            const res = await fetch(`${API_BASE}/library/manual-link`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    path,
                    tmdb_id: browsingJob.req ? browsingJob.req.tmdb_id : null,
                    media_type: browsingJob.media_type,
                    title: browsingJob.title,
                    year: browsingJob.req ? browsingJob.req.year : (browsingJob.year || ""),
                    season_number: browsingJob.season,
                    job_id: browsingJob.job_id
                })
            });
            if (res.ok) {
                addLog(`¡Vínculo manual exitoso!`);
                showNotification(`¡Vínculo manual exitoso! "${browsingJob.title}" ya está en la librería.`, "success");

                // Actualizar estado local para que se ponga en VERDE inmediatamente
                if (browsingJob.media_type === 'movie') {
                    setSymlinkExists(true);
                } else if (browsingJob.media_type === 'tv' && browsingJob.episode) {
                    setEpisodeSyncStatus(prev => ({ ...prev, [browsingJob.episode!]: 'synced' }));
                }

                setShowTorBoxBrowser(false);
                setBrowsingJob(null);
            } else {
                const err = await res.json();
                addLog(`Error en vínculo manual: ${err.detail}`);
                showNotification(`Error: ${err.detail}`, "error");
            }
        } catch (err) {
            addLog(`Error de red en vínculo manual: ${err}`);
        }
    };

    const handlePauseJob = async (id: string) => {
        try { await fetch(`${API_BASE}/downloads/${id}/pause`, { method: "POST" }); } catch (e) { }
    };

    const handleResumeJob = async (id: string) => {
        try { await fetch(`${API_BASE}/downloads/${id}/resume`, { method: "POST" }); } catch (e) { }
    };

    const handleDeleteJob = async (id: string) => {
        if (!confirm("¿Seguro que quieres detener y eliminar este trabajo?")) return;
        try { await fetch(`${API_BASE}/downloads/${id}`, { method: "DELETE" }); } catch (e) { }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setCurrentPage(1);
        fetchDiscovery(discoveryType, selectedGenre, 1, false, true);
        setActiveTab('search');
        addLog(`Buscando en TMDB: "${query}"`);
    };

    const fetchLibrary = async () => {
        setLoadingLibrary(true);
        addLog(`Consultando librería local (Symlinks)...`);
        try {
            const res = await fetch(`${API_BASE}/library`);
            const data = await res.json();
            setLibraryData(data);
            addLog(`Librería cargada: ${data.movies?.length || 0} películas, ${data.shows?.length || 0} series.`);
        } catch (err) {
            addLog(`Error leyendo librería: ${err}`);
        } finally {
            setLoadingLibrary(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'library') {
            fetchLibrary();
        }
    }, [activeTab]);

    const openLibraryStructure = async (item: { name: string, tmdb_id: number }, mediaType: string) => {
        setLibStructItem({ name: item.name, media_type: mediaType, tmdb_id: item.tmdb_id });
        setLibStructData([]);
        setLibStructDetails(null);
        setSymlinkStatuses({});
        setShowLibStruct(true);
        setLoadingStruct(true);
        try {
            // Fetch both structure and full details in parallel
            const [structRes, detailsRes] = await Promise.all([
                fetch(`${API_BASE}/library/structure?media_type=${mediaType}&folder_name=${encodeURIComponent(item.name)}`),
                fetch(`${API_BASE}/details/${mediaType}/${item.tmdb_id}`)
            ]);

            if (structRes.ok) {
                const data = await structRes.json();
                setLibStructData(data.structure || []);
            }
            if (detailsRes.ok) {
                const detData = await detailsRes.json();
                setLibStructDetails(detData);
            }
        } catch (err) {
            addLog(`Error cargando estructura/detalles: ${err}`);
        } finally {
            setLoadingStruct(false);
        }
    };

    const testSymlink = async (fullPath: string) => {
        setSymlinkStatuses(prev => ({ ...prev, [fullPath]: 'testing' }));
        try {
            const res = await fetch(`${API_BASE}/library/test_symlink`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath: fullPath })
            });
            if (res.ok) {
                const data = await res.json();
                setSymlinkStatuses(prev => ({ ...prev, [fullPath]: data.alive ? 'alive' : 'dead' }));
            } else {
                setSymlinkStatuses(prev => ({ ...prev, [fullPath]: 'dead' }));
            }
        } catch (err) {
            setSymlinkStatuses(prev => ({ ...prev, [fullPath]: 'dead' }));
        }
    };

    const deleteSymlink = async (fullPath: string) => {
        if (!confirm("¿Seguro que deseas eliminar este archivo de Plex?")) return;

        try {
            const res = await fetch(`${API_BASE}/library/symlink`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath: fullPath })
            });
            if (res.ok) {
                addLog(`Symlink eliminado: ${fullPath}`);
                // Refrescar el árbol
                if (libStructItem) {
                    openLibraryStructure(libStructItem, libStructItem.media_type);
                }
            } else {
                alert("Error eliminando el symlink.");
            }
        } catch (err) {
            alert(`Error de red: ${err}`);
        }
    };

    const deleteEntireSeason = async (seasonNumber: number) => {
        if (!confirm(`¿Eliminar TODA la temporada ${seasonNumber}? Esta acción no se puede deshacer.`)) return;

        try {
            const res = await fetch(`${API_BASE}/library/delete-season`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    media_type: libStructItem?.media_type, 
                    folder_name: libStructItem?.name,
                    season_number: seasonNumber
                })
            });
            if (res.ok) {
                addLog(`Temporada ${seasonNumber} eliminada completamente`);
                addGlobalNotification(`Temporada ${seasonNumber} eliminada`, 'success');
                if (libStructItem) {
                    openLibraryStructure(libStructItem, libStructItem.media_type);
                }
            } else {
                alert("Error eliminando la temporada.");
            }
        } catch (err) {
            alert(`Error de red: ${err}`);
        }
    };

    const deleteEntireSeries = async () => {
        if (!confirm(`¿Eliminar TODA la serie "${libStructItem?.name}"? Esta acción no se puede deshacer.`)) return;

        try {
            const res = await fetch(`${API_BASE}/library/delete-entire-series`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    media_type: libStructItem?.media_type,
                    folder_name: libStructItem?.name
                })
            });
            if (res.ok) {
                addLog(`Serie ${libStructItem?.name} eliminada completamente`);
                addGlobalNotification(`Serie eliminada`, 'success');
                setShowLibStruct(false);
                setLibStructItem(null);
            } else {
                alert("Error eliminando la serie.");
            }
        } catch (err) {
            alert(`Error de red: ${err}`);
        }
    };

    const deleteEntireMovie = async () => {
        if (!confirm(`¿Eliminar la película "${libStructItem?.name}"? Esta acción no se puede deshacer.`)) return;

        try {
            const res = await fetch(`${API_BASE}/library/delete-entire-movie`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    folder_name: libStructItem?.name
                })
            });
            if (res.ok) {
                addLog(`Película ${libStructItem?.name} eliminada completamente`);
                addGlobalNotification(`Película eliminada`, 'success');
                setShowLibStruct(false);
                setLibStructItem(null);
            } else {
                alert("Error eliminando la película.");
            }
        } catch (err) {
            alert(`Error de red: ${err}`);
        }
    };

    const getSymlinkInfo = async (fullPath: string) => {
        try {
            const res = await fetch(`${API_BASE}/library/symlink_info`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath: fullPath })
            });
            if (res.ok) {
                const data = await res.json();
                setSelectedSymlinkInfo(data);
            } else {
                alert("Error obteniendo información del symlink.");
            }
        } catch (err) {
            alert(`Error de red: ${err}`);
        }
    };

    const checkSymlink = async (item: any, seasonNumber: number | null = null, episodeNumber: number | null = null) => {
        try {
            const res = await fetch(`${API_BASE}/symlink/exists`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: item.title,
                    year: item.year,
                    media_type: item.media_type,
                    tmdb_id: item.id || item.tmdb_id,
                    season_number: seasonNumber,
                    episode_number: episodeNumber
                })
            });
            const data = await res.json();
            return data.exists;
        } catch {
            return false;
        }
    };

    const handleSelect = async (item: any) => {
        setSelectedItem(item);
        setMediaDetails(null);
        setSelectedSeason(null);
        setEpisodes([]);
        setStreams([]);
        setShowDetails(true);
        addLog(`Consultando detalles para: ${item.title}`);

        // Intentar obtener original_title si no viene
        if (!item.original_title && item.id) {
            // Se llenará cuando lleguen los detalles
        }

        // Verificar symlink base primero (si es peli esto es exacto, si es serie dice si existe la carpeta principal)
        const exists = await checkSymlink(item);
        setSymlinkExists(exists);

        try {
            const res = await fetch(`${API_BASE}/details/${item.media_type}/${item.id}`);
            if (res.ok) {
                const data = await res.json();
                setMediaDetails(data);
                if (data.original_title) {
                    setSelectedItem((prev: any) => ({ ...prev, original_title: data.original_title }));
                }
                // Si es serie, pre-seleccionar la primera temporada válida si existe
                if (item.media_type === 'tv' && data.seasons?.length > 0) {
                    handleSeasonSelect(item, data.seasons[0].season_number);
                } else if (item.media_type === 'movie') {
                    // Si es película, traemos streams de una vez (opcional, o ponemos un botón)
                    fetchStreams(item.media_type, item.id);
                }
            }
        } catch (err) {
            addLog(`Error al obtener detalles: ${err}`);
        }
    };

    const handleSeasonSelect = async (item: any, seasonNumber: number) => {
        // item can be either the full selectedItem or just an object with {id, title, year, media_type}
        const tmdb_id = typeof item === 'object' ? item.id : item;
        const media_item = typeof item === 'object' ? item : selectedItem;

        setSelectedSeason(seasonNumber);
        setEpisodes([]);
        setStreams([]); // Reset streams when changing season
        setEpisodeSyncStatus({}); // Reset statuses
        try {
            const res = await fetch(`${API_BASE}/season/${tmdb_id}/${seasonNumber}`);
            if (res.ok) {
                const data = await res.json();
                const foundEpisodes = data.episodes || [];
                setEpisodes(foundEpisodes);

                // Batch check symlinks for the season
                foundEpisodes.forEach(async (ep: any) => {
                    const exists = await checkSymlink(media_item, seasonNumber, ep.episode_number);
                    if (exists) {
                        setEpisodeSyncStatus(prev => ({ ...prev, [ep.episode_number]: 'synced' }));
                    }
                });
            }
        } catch (err) {
            addLog(`Error al obtener episodios de S${seasonNumber}: ${err}`);
        }
    };

    const fetchStreams = async (mediaType: string, tmdbId: number | string) => {
        setLoadingStreams(true);
        setStreams([]);
        setStreamCacheStatuses({});
        addLog(`Obteniendo fuentes de AIOStreams para ID: ${tmdbId}`);
        try {
            const res = await fetch(`${API_BASE}/streams/${mediaType}/${tmdbId}`);
            if (res.ok) {
                const data = await res.json();
                const fetchedStreams = data.streams || [];
                setStreams(fetchedStreams);
                addLog(`${fetchedStreams.length} streams encontrados.`);

                // Detectar caché por el indicador ⚡ en el nombre (AIOStreams marca con [TB⚡] los archivos en caché)
                const cacheStatuses: Record<string, boolean> = {};
                fetchedStreams.forEach((stream: any) => {
                    const id = stream.url || stream.title;
                    const streamName = stream.name || "";
                    
                    // Si el nombre contiene ⚡ está en caché según AIOStreams
                    if (streamName.includes("⚡") || streamName.includes("[TB⚡]")) {
                        cacheStatuses[id] = true;
                        addLog(`Stream en caché detectado: ${streamName.substring(0, 50)}...`);
                    } else {
                        cacheStatuses[id] = false;
                    }
                });
                setStreamCacheStatuses(cacheStatuses);
            }
        } catch (err) {
            addLog(`Error al obtener streams: ${err}`);
        } finally {
            setLoadingStreams(false);
        }
    };

    const getFilenameEstimate = (stream: any) => {
        const videoExts = ['.mkv', '.mp4', '.avi', '.ts', '.webm'];
        let filenameEstimate = stream.behaviorHints?.filename;
        if (!filenameEstimate && stream.url) {
            const urlParts = stream.url.split('/');
            for (let i = urlParts.length - 1; i >= 0; i--) {
                const seg = decodeURIComponent(urlParts[i]);
                if (videoExts.some(ext => seg.toLowerCase().endsWith(ext))) {
                    filenameEstimate = seg;
                    break;
                }
            }
        }
        return filenameEstimate || `Unknown_${selectedItem?.id}.mkv`;
    };

    // Este es para cuando das click a un episodio de serie específico
    const handleEpisodeSelect = async (episodeNumber: number) => {
        if (!selectedItem || !selectedSeason) return;

        // 1. Set current episode context (we overwrite selectedItem id temporarily for the stream fetcher? No, Stremio logic)
        // Wait, AIOStreams Addons use format: tmdb:12345:1:2 for TV Shows!
        // Right now our backend expects the base TMDB id and it hits /stream/tv/id.json
        // Let's modify the frontend to just send the episode to backend, or better yet:
        // AIOStreams works by sending /stream/tv/tt12345:1:2.json
        // Wait, we need to adjust our backend `get_streams` to support episode strings in the tmdb_id!
        // Let's do a quick hack string: ID:S:E

        const compoundId = `${selectedItem.id}:${selectedSeason}:${episodeNumber}`;

        // Check symlink immediately
        const exists = await checkSymlink(selectedItem, selectedSeason, episodeNumber);
        setSymlinkExists(exists);

        // Also save the episode context so we know what to send to watcher
        setSelectedItem({
            ...selectedItem,
            current_season: selectedSeason,
            current_episode: episodeNumber
        });

        fetchStreams('tv', compoundId as any);
    };

    const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
        setGlobalNotification({ message, type });
        setTimeout(() => setGlobalNotification(null), 4000);
    };

    const handleDownload = async (stream: any) => {
        const streamId = stream.url || stream.title;
        setDownloadingStreamId(streamId);

        // Obtenemos el filename real que TorBox debería usar
        const filenameEstimate = getFilenameEstimate(stream);

        addLog(`Contactando AIOStreams para detonar descarga en TorBox...`);

        addLog(`Contactando AIOStreams para detonar descarga en TorBox...`);
        // Detonamos la descarga simulando que un reproductor intenta acceder al stream
        if (stream.url) {
            fetch(stream.url, { method: "HEAD", mode: "no-cors" }).catch(() => { });
        }

        addLog(`Iniciando watcher para: ${filenameEstimate}`);
        try {
            await fetch(`${API_BASE}/download`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: selectedItem.title,
                    original_title: selectedItem.original_title,
                    year: selectedItem.year,
                    media_type: selectedItem.media_type,
                    tmdb_id: selectedItem.id,
                    filename: filenameEstimate,
                    season_number: selectedItem.current_season,
                    episode_number: selectedItem.current_episode
                })
            });
            addLog(`Instrucción enviada. Esperando a que Rclone monte el archivo...`);
            showNotification(`¡Añadido! Buscando "${selectedItem.title}" en la nube...`, 'success');

            // setItem status locally to show feedback immediately
            if (selectedItem.media_type === 'tv' && selectedItem.current_episode) {
                setEpisodeSyncStatus(prev => ({ ...prev, [selectedItem.current_episode]: 'pending' }));
            } else if (selectedItem.media_type === 'movie') {
                setSymlinkExists(true); // Pretend it exists to show synced state
            }
            // NO cerramos el modal: setSelectedItem(null); 
            setShowDetails(true);
        } catch (err) {
            addLog(`Error iniciando watcher: ${err}`);
            showNotification(`Error: ${err}`, 'error');
        } finally {
            setDownloadingStreamId(null);
        }
    }

    const handleOpenManualLink = (season?: number, episode?: number) => {
        const jobId = `${selectedItem.id}_${season || 0}_${episode || 0}`;
        setBrowsingJob({
            media_type: selectedItem.media_type,
            title: selectedItem.title,
            year: selectedItem.year,
            season: season,
            episode: episode,
            job_id: jobId,
            req: {
                tmdb_id: selectedItem.id,
                year: selectedItem.year
            }
        });
        setShowTorBoxBrowser(true);
        addLog(`Abriendo explorador de TorBox para vínculo manual: ${selectedItem.title}${season ? ` S${season}E${episode}` : ''}`);
    };

    const handleActorClick = async (personId: number) => {
        setPersonDetailsLoading(true);
        setSelectedPerson(null);
        setPersonCredits([]);

        try {
            // Fetch bio
            const bioRes = await fetch(`${API_BASE}/tmdb/person/${personId}`);
            if (bioRes.ok) {
                const bioData = await bioRes.json();
                setSelectedPerson(bioData);
            }

            // Fetch credits
            const credRes = await fetch(`${API_BASE}/tmdb/person/${personId}/credits`);
            if (credRes.ok) {
                const credData = await credRes.json();
                setPersonCredits(credData.results || []);
            }
        } catch (err) {
            addLog(`Error fetching person details: ${err}`);
        } finally {
            setPersonDetailsLoading(false);
        }
    };

    const renderStreamsList = () => {
        if (loadingStreams) {
            return (
                <div className="flex flex-col items-center justify-center p-8 space-y-4">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500"></div>
                    <p className="text-zinc-500 text-sm">Consultando AIOStreams...</p>
                </div>
            );
        }

        if (streams.length === 0) {
            return (
                <div className="text-center p-8 text-zinc-500 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                    No se encontraron fuentes de video para esta selección.
                </div>
            );
        }

        return (
            <div className="space-y-3">
                {streams.map((stream, idx) => {
                    const streamId = stream.url || stream.title;
                    const isCached = streamCacheStatuses[streamId];
                    const isDownloading = downloadingStreamId === streamId;

                    return (
                        <div key={idx} className={`flex items-center justify-between p-4 rounded-xl bg-zinc-900 border transition-all group shadow-md shadow-black/20 ${isCached ? "border-emerald-500/30 hover:border-emerald-500/50" : "border-zinc-800 hover:border-amber-500/50"}`}>
                            <div className="flex-1 min-w-0 pr-4">
                                <div className="flex items-center gap-2">
                                    <h4 className="font-medium text-zinc-200">{stream.name || "AIOStream"}</h4>
                                    {isCached && (
                                        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase tracking-wider border border-emerald-500/20">
                                            <Zap className="w-3 h-3 fill-emerald-400" />
                                            En Caché
                                        </span>
                                    )}
                                </div>
                                <p className="text-sm text-zinc-500 mt-2 whitespace-pre-wrap leading-relaxed truncate">
                                    {stream.description || stream.title}
                                </p>
                                {stream.behaviorHints?.videoSize && (
                                    <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-1 bg-zinc-800 rounded font-mono text-xs text-amber-500/70 border border-amber-500/10">
                                        <Activity className="w-3 h-3" />
                                        {(stream.behaviorHints.videoSize / (1024 * 1024 * 1024)).toFixed(2)} GB
                                    </div>
                                )}
                            </div>
                            <button
                                onClick={() => handleDownload(stream)}
                                disabled={isDownloading}
                                className={`shrink-0 flex items-center gap-2 font-bold px-4 py-2.5 rounded-lg transition-all active:scale-95 shadow-lg ${isDownloading
                                    ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
                                    : isCached
                                        ? "bg-emerald-500 hover:bg-emerald-400 text-zinc-950 shadow-emerald-500/20"
                                        : "bg-amber-500 hover:bg-amber-400 text-zinc-950 shadow-amber-500/20"
                                    }`}
                            >
                                {isDownloading ? (
                                    <>
                                        <Activity className="w-4 h-4 animate-spin" />
                                        Iniciando...
                                    </>
                                ) : isCached ? (
                                    <>
                                        <Zap className="w-4 h-4 fill-current" />
                                        Añadir a Plex
                                    </>
                                ) : (
                                    <>
                                        <Download className="w-4 h-4" />
                                        Descargar
                                    </>
                                )}
                            </button>
                        </div>
                    );
                })}
            </div>
        );
    };

    if (checkingStatus) {
        return (
            <div className="fixed inset-0 bg-zinc-950 flex flex-col items-center justify-center text-amber-500 gap-4">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-amber-500"></div>
                <p className="font-mono text-sm tracking-widest text-zinc-500">Iniciando PlexAioTorb...</p>
            </div>
        );
    }

    if (setupMode) {
        return (
            <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-6 text-slate-200">
                <div className="max-w-xl w-full bg-zinc-900 border border-zinc-800 rounded-3xl p-10 shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-amber-500 via-yellow-500 to-orange-500"></div>

                    <div className="flex items-center gap-4 mb-10">
                        <div className="w-12 h-12 rounded-xl bg-amber-500 flex items-center justify-center text-zinc-950 font-bold text-2xl shadow-lg shadow-amber-500/20">P</div>
                        <div>
                            <h1 className="text-3xl font-medium tracking-tight">Bienvenido a <span className="bg-clip-text text-transparent bg-gradient-to-r from-amber-400 to-orange-400">PlexAioTorb</span></h1>
                            <p className="text-zinc-500 text-sm mt-1">Configuremos tu centro multimedia automático.</p>
                        </div>
                    </div>

                    <div className="space-y-6">
                        {setupStep === 1 && (
                            <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-500">
                                <h2 className="text-lg font-medium text-amber-400">1. APIS y Metadatos</h2>
                                <div>
                                    <label className="block text-sm text-zinc-400 mb-1">TMDb API Key (V3)</label>
                                    <input type="text" value={setupData.tmdb_api_key} onChange={e => setSetupData({ ...setupData, tmdb_api_key: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 focus:ring-2 focus:ring-amber-500/50 outline-none" placeholder="ej. abc123def456..." />
                                </div>
                                <div>
                                    <label className="block text-sm text-zinc-400 mb-1">AIOStreams Internal URL</label>
                                    <input type="url" value={setupData.aiostreams_url} onChange={e => setSetupData({ ...setupData, aiostreams_url: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 focus:ring-2 focus:ring-amber-500/50 outline-none" placeholder="http://192.168.1.100:puerto" />
                                </div>
                                <button onClick={() => setSetupStep(2)} className="w-full py-3 mt-4 bg-zinc-100 hover:bg-white text-zinc-900 font-bold rounded-lg transition-colors">Siguiente</button>
                            </div>
                        )}

                        {setupStep === 2 && (
                            <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-500">
                                <h2 className="text-lg font-medium text-amber-400">2. Túnel WebDAV (TorBox)</h2>
                                <p className="text-xs text-zinc-500">Tus datos se ofuscarán automáticamente usando Rclone. Nosotros no los vemos.</p>
                                <div>
                                    <label className="block text-sm text-zinc-400 mb-1">TorBox Email</label>
                                    <input type="email" value={setupData.torbox_email} onChange={e => setSetupData({ ...setupData, torbox_email: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 focus:ring-2 focus:ring-amber-500/50 outline-none" />
                                </div>
                                <div>
                                    <label className="block text-sm text-zinc-400 mb-1">TorBox Password</label>
                                    <input type="password" value={setupData.torbox_password} onChange={e => setSetupData({ ...setupData, torbox_password: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 focus:ring-2 focus:ring-amber-500/50 outline-none" />
                                </div>
                                <div className="flex gap-4 mt-4">
                                    <button onClick={() => setSetupStep(1)} className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold rounded-lg transition-colors">Atrás</button>
                                    <button onClick={() => setSetupStep(3)} className="flex-1 py-3 bg-zinc-100 hover:bg-white text-zinc-900 font-bold rounded-lg transition-colors">Siguiente</button>
                                </div>
                            </div>
                        )}

                        {setupStep === 3 && (
                            <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-500">
                                <h2 className="text-lg font-medium text-amber-400">3. Plex Media Server</h2>
                                <p className="text-xs text-zinc-500">Configura el nombre de tu servidor Plex. Podrás reclamarlo directamente entrando a {`http://${HOST}:32400/web`} después de iniciar.</p>
                                <div>
                                    <label className="block text-sm text-zinc-400 mb-1">Nombre del Servidor Plex</label>
                                    <input type="text" value={setupData.plex_server_name} onChange={e => setSetupData({ ...setupData, plex_server_name: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 focus:ring-2 focus:ring-amber-500/50 outline-none" placeholder="Ej. Mi Servidor Plex" />
                                </div>

                                {setupMessage ? (
                                    <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/50 text-amber-400 text-sm text-center font-medium mt-6 animate-pulse">
                                        {setupMessage}
                                    </div>
                                ) : (
                                    <div className="flex gap-4 mt-6">
                                        <button onClick={() => setSetupStep(2)} className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold rounded-lg transition-colors">Atrás</button>
                                        <button onClick={handleSetupSubmit} className="flex-1 py-3 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold shadow-lg shadow-amber-500/30 rounded-lg transition-all">Finalizar & Reiniciar Todo</button>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-zinc-950 flex font-sans">
            {/* Toast Notifications */}
            <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-3 pointer-events-none">
                {notifications.map((msg, idx) => (
                    <div key={idx} className="bg-zinc-900 border border-green-500/30 text-green-500 px-6 py-3 rounded-full shadow-2xl shadow-green-500/10 flex items-center gap-3 animate-in fade-in slide-in-from-top-4 duration-300">
                        <CheckCircle2 className="w-5 h-5" />
                        <span className="font-semibold text-sm">{msg}</span>
                    </div>
                ))}
            </div>

            {/* Left Navigation Sidebar */}
            <aside className="w-72 border-r border-zinc-800 bg-zinc-900/30 flex flex-col shrink-0">
                <div className="p-6 border-b border-zinc-800/50">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-amber-500 flex items-center justify-center text-zinc-950 font-bold shadow-lg shadow-amber-500/20">P</div>
                        <h1 className="text-xl font-medium tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-amber-400 to-amber-200">
                            PlexAioTorb
                        </h1>
                    </div>
                </div>

                <nav className="p-4 space-y-2">
                    <button
                        onClick={() => setActiveTab('search')}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${activeTab === 'search' ? 'bg-amber-500 text-zinc-950 shadow-md shadow-amber-500/10' : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'}`}
                    >
                        <Search className="w-5 h-5" /> Buscar Contenido
                    </button>
                    <button
                        onClick={() => setActiveTab('activity')}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${activeTab === 'activity' ? 'bg-amber-500 text-zinc-950 shadow-md shadow-amber-500/10' : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'}`}
                    >
                        <Activity className="w-5 h-5" /> Actividad {Object.keys(activeDownloads).length > 0 && <span className="ml-auto bg-amber-500/20 text-amber-500 text-[10px] px-2 py-0.5 rounded-full">{Object.keys(activeDownloads).length}</span>}
                    </button>
                    <button
                        onClick={() => setActiveTab('library')}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${activeTab === 'library' ? 'bg-amber-500 text-zinc-950 shadow-md shadow-amber-500/10' : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'}`}
                    >
                        <Film className="w-5 h-5" /> Mi Librería
                    </button>
                </nav>

                {/* --- SECCIÓN PARA MOSTRAR RÁPIDO SI HAY ALGO (OPCIONAL) --- */}
                {Object.keys(activeDownloads).length > 0 && (
                    <div className="px-6 py-4 border-t border-zinc-800/50 mt-auto">
                        <div className="flex items-center justify-between text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2">
                            <span>Sincronizando</span>
                            <span className="text-amber-500">{Object.keys(activeDownloads).length}</span>
                        </div>
                        <div className="h-1 w-full bg-zinc-800 rounded-full overflow-hidden">
                            <div className="h-full bg-amber-500 animate-pulse w-1/3"></div>
                        </div>
                        <p className="text-[9px] text-zinc-600 mt-2 italic text-center">Mira la pestaña de Actividad para más detalles</p>
                    </div>
                )}

                <div className="p-4 border-t border-zinc-800/50 space-y-4">
                    <div className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-zinc-800/30 border border-zinc-700/30 text-xs font-medium w-full">
                        {rcloneStatus === 'connected' ? <CheckCircle2 className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-red-500" />}
                        <span className={rcloneStatus === 'connected' ? 'text-green-500' : 'text-red-500'}>
                            {rcloneStatus === 'connected' ? 'Rclone Montado' : 'Rclone Error'}
                        </span>
                    </div>
                    <button
                        onClick={() => setShowSettings(true)}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2 text-zinc-400 hover:text-amber-400 hover:bg-zinc-800 rounded-lg transition-colors text-sm font-medium"
                    >
                        <Settings className="w-4 h-4" /> Configuración
                    </button>
                </div>
            </aside>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col overflow-hidden">

                {/* Top Search Header */}
                <header className="sticky top-0 z-10 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800/50 px-6 py-4 flex items-center justify-between min-h-[73px]">
                    <div className="flex-1 max-w-2xl">
                        {activeTab === 'search' ? (
                            <form onSubmit={handleSearch} className="relative">
                                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
                                <input
                                    type="text"
                                    placeholder="Buscar películas, series..."
                                    value={query}
                                    onChange={(e) => {
                                        setQuery(e.target.value);
                                        if (!e.target.value) {
                                            // Trigger refetch of discovery if query cleared
                                            fetchDiscovery(discoveryType, selectedGenre);
                                        }
                                    }}
                                    className="w-full bg-zinc-900 border border-zinc-700/50 rounded-full py-3 pl-12 pr-4 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50 transition-all font-medium shadow-inner"
                                />
                            </form>
                        ) : (
                            <h2 className="text-xl font-bold text-zinc-100">Vista de Librería Local</h2>
                        )}
                    </div>
                </header>

                <main className="flex-1 flex overflow-hidden">

                    {/* Dynamic Content Area */}
                    <div className={`flex-1 ${selectedItem || selectedPerson ? 'overflow-hidden' : 'overflow-y-auto'} p-6`}>
                        {activeTab === 'search' ? (
                            <div className="space-y-12">
                                {/* 1. Trending Row (Only if no search query) */}
                                {!query && trendingMedia.length > 0 && (
                                    <section className="animate-in fade-in slide-in-from-top-4 duration-1000">
                                        <div className="flex items-center justify-between mb-4">
                                            <h2 className="text-xl font-black text-zinc-100 uppercase tracking-tight flex items-center gap-2">
                                                <Activity className="w-5 h-5 text-amber-500" />
                                                Tendencias de la Semana
                                            </h2>
                                        </div>
                                        <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide -mx-2 px-2">
                                            {trendingMedia.slice(0, 10).map((item) => (
                                                <div
                                                    key={`${item.id}-${item.media_type}`}
                                                    onClick={() => handleSelect(item)}
                                                    className="flex-none w-64 group cursor-pointer"
                                                >
                                                    <div className="relative aspect-video rounded-xl overflow-hidden bg-zinc-800 border border-zinc-700/50 shadow-lg transition-transform duration-300 group-hover:scale-105">
                                                        <img
                                                            src={item.backdrop_path || item.poster_path}
                                                            className="w-full h-full object-cover"
                                                            alt={item.title}
                                                        />
                                                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                                                        <div className="absolute bottom-3 left-4 right-4">
                                                            <h3 className="text-white font-bold text-sm truncate">{item.title}</h3>
                                                            <div className="flex items-center gap-2 mt-1">
                                                                <span className="text-amber-500 text-[10px] font-black">★ {item.vote_average}</span>
                                                                <span className="text-zinc-400 text-[10px] uppercase font-bold">{item.media_type === 'movie' ? 'Película' : 'Serie'}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </section>
                                )}

                                {/* 2. Discovery Filters */}
                                {!query && (
                                    <div className="sticky top-[0px] z-10 py-4 bg-zinc-950/95 backdrop-blur-md -mx-6 px-6 flex flex-col gap-4 border-b border-zinc-900 shadow-xl">
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => { setDiscoveryType('movie'); setSelectedGenre(null); }}
                                                className={`px-4 py-1.5 rounded-full text-xs font-black uppercase tracking-widest transition-all ${discoveryType === 'movie' ? 'bg-amber-500 text-zinc-950' : 'bg-zinc-900 text-zinc-500 hover:text-zinc-300 border border-zinc-800'}`}
                                            >
                                                Películas
                                            </button>
                                            <button
                                                onClick={() => { setDiscoveryType('tv'); setSelectedGenre(null); }}
                                                className={`px-4 py-1.5 rounded-full text-xs font-black uppercase tracking-widest transition-all ${discoveryType === 'tv' ? 'bg-amber-500 text-zinc-950' : 'bg-zinc-900 text-zinc-500 hover:text-zinc-300 border border-zinc-800'}`}
                                            >
                                                Series
                                            </button>
                                        </div>

                                        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                                            <button
                                                onClick={() => setSelectedGenre(null)}
                                                className={`flex-none px-3 py-1 rounded-lg text-[10px] font-bold uppercase transition-all ${!selectedGenre ? 'bg-zinc-100 text-zinc-950' : 'bg-zinc-900 text-zinc-500 hover:bg-zinc-800'}`}
                                            >
                                                Todos
                                            </button>
                                            {genres.map(g => (
                                                <button
                                                    key={g.id}
                                                    onClick={() => setSelectedGenre(g.id)}
                                                    className={`flex-none px-3 py-1 rounded-lg text-[10px] font-bold uppercase transition-all ${selectedGenre === g.id ? 'bg-zinc-100 text-zinc-950' : 'bg-zinc-900 text-zinc-500 hover:bg-zinc-800'}`}
                                                >
                                                    {g.name}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* 3. Main Results */}
                                <div>
                                    {!query && (
                                        <h2 className="text-sm font-black text-zinc-500 uppercase tracking-widest mb-6 px-1">
                                            {selectedGenre ? genres.find(g => g.id === selectedGenre)?.name : 'Más populares'}
                                        </h2>
                                    )}
                                    {loading || discoveryLoading ? (
                                        <div className="flex items-center justify-center h-64">
                                            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500"></div>
                                        </div>
                                    ) : results.length > 0 ? (
                                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
                                            {results.map(item => (
                                                <div
                                                    key={`${item.id}-${item.media_type}`}
                                                    onClick={() => handleSelect(item)}
                                                    className="group relative flex flex-col gap-2 cursor-pointer"
                                                >
                                                    <div className="relative aspect-[2/3] rounded-lg overflow-hidden bg-zinc-800 border border-zinc-700/50 transition-transform duration-300 group-hover:scale-105 group-hover:ring-2 group-hover:ring-amber-500/50 shadow-lg">
                                                        {item.poster_path ? (
                                                            <img src={item.poster_path} alt={item.title} className="w-full h-full object-cover" />
                                                        ) : (
                                                            <div className="w-full h-full flex items-center justify-center text-zinc-600">No Image</div>
                                                        )}
                                                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                                                            <Play className="w-12 h-12 text-white fill-white/20" />
                                                            {item.vote_average > 0 && (
                                                                <span className="text-amber-500 text-xs font-black">★ {item.vote_average}</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <h3 className="font-medium text-zinc-100 line-clamp-1 group-hover:text-amber-400 transition-colors">
                                                            {item.title}
                                                        </h3>
                                                        <div className="flex items-center gap-2 text-xs text-zinc-400">
                                                            {item.media_type === 'movie' ? <Film className="w-3 h-3" /> : <Tv className="w-3 h-3" />}
                                                            <span>{item.year || 'N/A'}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="flex flex-col items-center justify-center h-full text-zinc-500 py-20 space-y-4">
                                            <Search className="w-16 h-16 opacity-20" />
                                            <p>{query ? `No encontramos resultados para "${query}"` : 'No hay contenido disponible en este momento'}</p>
                                        </div>
                                    )}

                                    {/* Infinite Scroll Sentinel */}
                                    {results.length > 0 && hasMore && !selectedItem && !selectedPerson && (
                                        <div ref={observerTarget} className="flex justify-center py-8">
                                            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500"></div>
                                        </div>
                                    )}
                                    {results.length > 0 && !hasMore && (
                                        <div className="text-center py-8 text-zinc-500 text-sm">
                                            Has llegado al final de los resultados.
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : activeTab === 'activity' ? (
                            /* ----- ACTIVITY TABLE VIEW ----- */
                            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                <div className="flex items-center justify-between mb-8">
                                    <div>
                                        <h2 className="text-2xl font-black text-zinc-100 uppercase tracking-tight flex items-center gap-3">
                                            <Activity className="w-6 h-6 text-amber-500" />
                                            Procesos Activos
                                        </h2>
                                        <p className="text-zinc-500 text-sm mt-1">Supervisa y gestiona el estado de tus descargas en tiempo real.</p>
                                    </div>
                                    <div className="flex gap-2">
                                        <span className="bg-zinc-800 text-zinc-400 text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest border border-zinc-700">
                                            {Object.keys(activeDownloads).length} Trabajos
                                        </span>
                                    </div>
                                </div>

                                {Object.keys(activeDownloads).length === 0 ? (
                                    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-20 flex flex-col items-center justify-center gap-4 text-center grayscale">
                                        <div className="w-16 h-16 bg-zinc-800 rounded-full flex items-center justify-center">
                                            <Activity className="w-8 h-8 text-zinc-600" />
                                        </div>
                                        <div>
                                            <h3 className="text-zinc-400 font-bold uppercase text-xs tracking-widest">No hay actividad</h3>
                                            <p className="text-zinc-600 text-sm mt-1">Todo está tranquilo por aquí. Busca algo para empezar.</p>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="grid gap-4">
                                        {Object.entries(activeDownloads).map(([id, job]: [string, any]) => (
                                            <div key={id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 transition-all hover:bg-zinc-800/50 group">
                                                <div className="flex items-start justify-between gap-6">
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-3 mb-1">
                                                            <h3 className="text-lg font-bold text-zinc-100 truncate">{job.title}</h3>
                                                            <span className={`text-[10px] font-black px-2 py-0.5 rounded uppercase ${job.status === 'Completed' ? 'bg-green-500/10 text-green-500' :
                                                                job.status === 'Error' ? 'bg-red-500/10 text-red-500' :
                                                                    job.status === 'Paused' ? 'bg-yellow-500/10 text-yellow-500 animate-pulse' :
                                                                        'bg-amber-500/10 text-amber-500'
                                                                }`}>
                                                                {job.status}
                                                            </span>
                                                        </div>
                                                        <p className="text-sm text-zinc-500 flex items-center gap-2 mb-4">
                                                            {job.media_type === 'tv' ? <Tv className="w-3.5 h-3.5" /> : <Film className="w-3.5 h-3.5" />}
                                                            {job.media_type === 'tv' ? `Temporada ${job.season} Episodio ${job.episode}` : 'Largometraje'}
                                                        </p>

                                                        <div className="space-y-2">
                                                            <div className="flex justify-between items-end">
                                                                <span className="text-[10px] uppercase font-bold text-zinc-600 tracking-widest">Progreso del Sistema</span>
                                                                <span className="text-[10px] text-amber-500 font-mono italic">{job.message}</span>
                                                            </div>
                                                            <div className="relative h-2 w-full bg-zinc-800 rounded-full overflow-hidden">
                                                                <div
                                                                    className={`absolute inset-y-0 left-0 transition-all duration-1000 ${job.status === 'Completed' ? 'w-full bg-green-500' :
                                                                        job.status === 'Linking' ? 'w-2/3 bg-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.5)]' :
                                                                            'w-1/3 bg-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.5)]'
                                                                        }`}
                                                                />
                                                            </div>
                                                            {/* Log terminal expandible */}
                                                            {(() => {
                                                                const isExpanded = expandedJobLog === id;
                                                                const logs = jobLogs[id] || [];
                                                                return (
                                                                    <div className="mt-3">
                                                                        <button
                                                                            onClick={() => setExpandedJobLog(isExpanded ? null : id)}
                                                                            className="w-full flex items-center justify-between text-[10px] uppercase tracking-widest text-zinc-600 hover:text-amber-500 transition-colors py-1"
                                                                        >
                                                                            <span className="flex items-center gap-1.5">
                                                                                <span className="font-mono">&gt;_</span>
                                                                                Logs del Watcher
                                                                                {logs.length > 0 && <span className="bg-amber-500/20 text-amber-500 px-1.5 py-0.5 rounded text-[9px] font-bold">{logs.length}</span>}
                                                                            </span>
                                                                            <span>{isExpanded ? '▲' : '▼'}</span>
                                                                        </button>
                                                                        {isExpanded && (
                                                                            <div className="mt-2 bg-zinc-950 border border-zinc-800 rounded-xl p-3 max-h-64 overflow-y-auto font-mono text-[10px] leading-relaxed">
                                                                                {logs.length === 0 ? (
                                                                                    <p className="text-zinc-600 italic">Esperando logs...</p>
                                                                                ) : (
                                                                                    logs.map((line, i) => (
                                                                                        <div key={i} className={`
                                                                                            ${line.includes('ERROR') || line.includes('Error') ? 'text-red-400' : ''}
                                                                                            ${line.includes('✓') || line.includes('Éxito') || line.includes('Completado') ? 'text-green-400' : ''}
                                                                                            ${!line.includes('ERROR') && !line.includes('✓') && !line.includes('Éxito') && !line.includes('Completado') ? 'text-zinc-400' : ''}
                                                                                            ${line.includes('Debug') ? 'text-zinc-600' : ''}
                                                                                        `}>
                                                                                            {line}
                                                                                        </div>
                                                                                    ))
                                                                                )}
                                                                                <div ref={jobLogsEndRef} />
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                );
                                                            })()}
                                                        </div>
                                                    </div>

                                                    <div className="flex flex-col gap-2">
                                                        <div className="flex gap-2">
                                                            {job.status === 'Paused' ? (
                                                                <button onClick={() => handleResumeJob(id)} className="flex-1 px-4 py-2 bg-amber-500 text-zinc-950 font-bold rounded-xl text-xs flex items-center justify-center gap-2 hover:bg-amber-400 transition-all">
                                                                    <Play className="w-3.5 h-3.5 fill-current" /> Reanudar
                                                                </button>
                                                            ) : (job.status !== 'Completed' && job.status !== 'Error' && job.status !== 'Cancelled') && (
                                                                <button onClick={() => handlePauseJob(id)} className="flex-1 px-4 py-2 bg-zinc-800 text-zinc-300 font-bold rounded-xl text-xs flex items-center justify-center gap-2 hover:bg-zinc-700 transition-all">
                                                                    <Pause className="w-3.5 h-3.5 fill-current" /> Pausar
                                                                </button>
                                                            )}
                                                            <button onClick={() => handleDeleteJob(id)} className="px-4 py-2 bg-red-500/10 text-red-500 font-bold rounded-xl text-xs hover:bg-red-500/20 transition-all border border-red-500/20">
                                                                <Trash2 className="w-4 h-4" />
                                                            </button>
                                                        </div>
                                                        {job.status !== 'Completed' && job.status !== 'Cancelled' && (
                                                            <button
                                                                onClick={() => { setBrowsingJob({ ...job, job_id: id }); setShowTorBoxBrowser(true); }}
                                                                className="w-full py-2 bg-zinc-950/50 hover:bg-zinc-950 text-zinc-500 hover:text-amber-500 font-bold rounded-xl text-[10px] uppercase tracking-tighter border border-zinc-800 transition-all flex items-center justify-center gap-2"
                                                            >
                                                                <LinkIcon className="w-3.5 h-3.5" /> Enlace Manual
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ) : (
                            /* ----- LIBRARY GRID ----- */
                            loadingLibrary ? (
                                <div className="flex items-center justify-center h-64">
                                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500"></div>
                                </div>
                            ) : (
                                <div className="animate-in fade-in space-y-10">
                                    {/* Movies Section */}
                                    <div>
                                        <h2 className="text-xl font-bold text-zinc-100 mb-6 flex items-center gap-2 border-b border-zinc-800 pb-3">
                                            <Film className="w-5 h-5 text-amber-500" /> Películas Sincronizadas
                                            <span className="text-zinc-600 font-normal text-sm ml-2 bg-zinc-800/50 px-2 py-0.5 rounded-md">{libraryData.movies?.length || 0}</span>
                                        </h2>

                                        {libraryData.movies?.length > 0 ? (
                                            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 gap-6">
                                                {libraryData.movies.map((item, idx) => (
                                                    <LibraryItemCard key={idx} item={item} mediaType="movie" onClick={openLibraryStructure} />
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="text-zinc-600 text-sm italic">No hay películas sincronizadas aún.</p>
                                        )}
                                    </div>

                                    {/* Shows Section */}
                                    <div>
                                        <h2 className="text-xl font-bold text-zinc-100 mb-6 flex items-center gap-2 border-b border-zinc-800 pb-3">
                                            <Tv className="w-5 h-5 text-amber-500" /> Series Sincronizadas
                                            <span className="text-zinc-600 font-normal text-sm ml-2 bg-zinc-800/50 px-2 py-0.5 rounded-md">{libraryData.shows?.length || 0}</span>
                                        </h2>

                                        {libraryData.shows?.length > 0 ? (
                                            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 gap-6">
                                                {libraryData.shows.map((item, idx) => (
                                                    <LibraryItemCard key={idx} item={item} mediaType="tv" onClick={openLibraryStructure} />
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="text-zinc-600 text-sm italic">No hay series sincronizadas aún.</p>
                                        )}
                                    </div>
                                </div>
                            )
                        )}
                    </div>

                </main>
            </div>

            {/* Settings Modal */}
            {
                showSettings && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
                        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-4xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
                            <div className="p-6 border-b border-zinc-800 flex justify-between items-center">
                                <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
                                    <Settings className="w-5 h-5 text-amber-500" /> Ajustes y Consola
                                </h2>
                                <button onClick={() => setShowSettings(false)} className="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-full text-zinc-400 hover:text-white transition-colors">
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-zinc-800">
                                {/* Configuration Panel */}
                                <div className="p-6 space-y-5 lg:w-1/3 flex flex-col">
                                    <h3 className="font-semibold text-zinc-300 text-sm uppercase tracking-wide">Configuración en Vivo</h3>

                                    <div className="space-y-4 flex-1">
                                        <div className="space-y-2">
                                            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">TMDB API Key</label>
                                            <input
                                                type="password"
                                                value={settingsForm.tmdb_api_key}
                                                onChange={e => setSettingsForm({ ...settingsForm, tmdb_api_key: e.target.value })}
                                                className="w-full bg-black/50 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-amber-500/50 transition-colors placeholder:text-zinc-700"
                                                placeholder="Ingresa tu token de the movie database"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">AIOStreams URL Base</label>
                                            <input
                                                type="url"
                                                value={settingsForm.aiostreams_url}
                                                onChange={e => setSettingsForm({ ...settingsForm, aiostreams_url: e.target.value })}
                                                className="w-full bg-black/50 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-amber-500/50 transition-colors placeholder:text-zinc-700"
                                                placeholder="https://aiostreams.example.com"
                                            />
                                            <p className="text-[10px] text-zinc-500 font-medium">Requerido para generar enlaces Magnets o Streaming</p>
                                        </div>
                                    </div>

                                    <div className="pt-4 space-y-3 border-t border-zinc-800/50">
                                        <button
                                            onClick={handleSaveSettings}
                                            disabled={settingsSaving}
                                            className="w-full py-2.5 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold shadow-lg shadow-amber-500/20 rounded-lg transition-all flex justify-center items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {settingsSaving ? <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-zinc-950"></div> : <Settings className="w-4 h-4" />}
                                            Guardar Cambios
                                        </button>

                                        <button
                                            onClick={() => {
                                                setShowSettings(false);
                                                setSetupMode(true);
                                                setSetupStep(1);
                                            }}
                                            className="w-full py-2 bg-zinc-900 border border-red-500/20 text-red-400 hover:text-red-300 hover:bg-red-500/10 font-bold rounded-lg transition-all text-sm"
                                        >
                                            Asistente de Reseteo Total
                                        </button>
                                    </div>
                                </div>

                                {/* Logs Panel */}
                                <div className="p-6 flex-1 flex flex-col max-h-96 lg:max-h-full">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="font-semibold text-zinc-300 text-sm uppercase tracking-wide flex items-center gap-2">
                                            <Activity className="w-4 h-4 text-amber-500" /> Consola del Sistema
                                        </h3>
                                        <div className="flex bg-zinc-800 p-1 rounded-lg">
                                            <button
                                                onClick={() => setActiveLogTab('backend')}
                                                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${activeLogTab === 'backend' ? 'bg-amber-500 text-zinc-950' : 'text-zinc-400 hover:text-zinc-200'}`}
                                            >Backend / API</button>
                                            <button
                                                onClick={() => setActiveLogTab('rclone')}
                                                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${activeLogTab === 'rclone' ? 'bg-amber-500 text-zinc-950' : 'text-zinc-400 hover:text-zinc-200'}`}
                                            >Rclone / Plex</button>
                                            <button
                                                onClick={() => setActiveLogTab('local')}
                                                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${activeLogTab === 'local' ? 'bg-amber-500 text-zinc-950' : 'text-zinc-400 hover:text-zinc-200'}`}
                                            >GUI Local</button>
                                        </div>
                                    </div>

                                    <div className="flex-1 overflow-y-auto font-mono text-[11px] text-zinc-400 space-y-1 bg-black/50 p-4 rounded-lg border border-zinc-800/50">
                                        {activeLogTab === 'local' ? (
                                            /* Mostrar SOLO GUI Local logs */
                                            logs.length > 0 ? logs.map((log, i) => (
                                                <div key={`local-${i}`} className="leading-relaxed whitespace-pre-wrap break-words text-zinc-400 border-l-2 border-zinc-600 pl-2 py-0.5">
                                                    {log}
                                                </div>
                                            )) : <div className="text-zinc-600 italic">No hay logs locales...</div>

                                        ) : activeLogTab === 'backend' ? (
                                            /* Mostrar Backend Logs */
                                            globalLogs.filter(l => l.includes('plexaiotorb-backend')).length > 0 ?
                                                globalLogs.filter(l => l.includes('plexaiotorb-backend')).map((log, i) => (
                                                    <div key={`be-${i}`} className="leading-relaxed whitespace-pre-wrap break-words text-blue-200 border-l-2 border-blue-500 pl-2 py-0.5">
                                                        {log}
                                                    </div>
                                                )) : <div className="text-zinc-600 italic">Esperando eventos del backend...</div>

                                        ) : (
                                            /* Mostrar Rclone/Plex Logs */
                                            globalLogs.filter(l => !l.includes('plexaiotorb-backend')).length > 0 ?
                                                globalLogs.filter(l => !l.includes('plexaiotorb-backend')).map((log, i) => (
                                                    <div key={`rc-${i}`} className="leading-relaxed whitespace-pre-wrap break-words text-amber-200 border-l-2 border-amber-500 pl-2 py-0.5">
                                                        {log}
                                                    </div>
                                                )) : <div className="text-zinc-600 italic">Esperando eventos de rclone/plex...</div>
                                        )}

                                        <div ref={logsEndRef} />
                                    </div>
                                </div>
                            </div>

                        </div>
                    </div>
                )
            }

            {/* Details & Streams Modal */}
            {
                showDetails && selectedItem && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
                        <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-4xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh] relative">

                            {/* Hero Image Background */}
                            {mediaDetails?.backdrop_path && (
                                <div className="absolute top-0 inset-x-0 h-64 bg-zinc-900 pointer-events-none">
                                    <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/80 to-transparent z-10" />
                                    <img src={mediaDetails.backdrop_path} alt="Backdrop" className="w-full h-full object-cover opacity-50" />
                                </div>
                            )}

                            <div className="p-6 border-b border-zinc-900 flex justify-between items-start gap-4 relative z-20">
                                <div className="flex gap-6">
                                    {mediaDetails?.poster_path || selectedItem.poster_path ? (
                                        <img src={mediaDetails?.poster_path || selectedItem.poster_path} className="w-28 h-auto rounded-lg shadow-2xl ring-1 ring-white/10" alt="Poster" />
                                    ) : null}
                                    <div className="mt-2">
                                        <h2 className="text-3xl font-bold text-zinc-100 drop-shadow-md">
                                            {selectedItem.title}
                                            {selectedItem.year && (
                                                <span className="text-zinc-400 font-normal ml-2">({selectedItem.year})</span>
                                            )}
                                        </h2>

                                        <div className="flex items-center gap-3 mt-3 text-sm font-medium">
                                            {symlinkExists ? (
                                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-green-500/10 text-green-500 border border-green-500/20">
                                                    <CheckCircle2 className="w-4 h-4" /> Ya en Librería
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 text-zinc-400 border border-zinc-700">
                                                    <Film className="w-4 h-4" /> No Descargado
                                                </span>
                                            )}
                                            <button
                                                onClick={() => handleOpenManualLink()}
                                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-amber-500 border border-zinc-700 transition-colors cursor-pointer group"
                                                title="Vincular archivo manualmente desde TorBox"
                                            >
                                                <LinkIcon className="w-4 h-4 group-hover:scale-110 transition-transform" /> Vincular Manual
                                            </button>

                                            {mediaDetails?.vote_average > 0 && (
                                                <span className="text-amber-500 flex items-center gap-1">★ {mediaDetails.vote_average}</span>
                                            )}
                                        </div>

                                        {mediaDetails?.genres?.length > 0 && (
                                            <div className="flex gap-2 mt-3 flex-wrap">
                                                {mediaDetails.genres.map((g: string, i: number) => (
                                                    <span key={i} className="px-2 py-0.5 rounded text-xs bg-zinc-800/80 text-zinc-300 backdrop-blur">{g}</span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <button
                                    onClick={() => setShowDetails(false)}
                                    className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 hover:text-white transition-colors cursor-pointer z-30"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className="overflow-y-auto flex-1 bg-zinc-950 relative z-20">
                                {!mediaDetails ? (
                                    <div className="flex flex-col items-center justify-center p-12 space-y-4">
                                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500"></div>
                                        <p className="text-zinc-500 text-sm">Cargando detalles...</p>
                                    </div>
                                ) : (
                                    <div className="p-6 space-y-8">

                                        {/* Overview & Cast */}
                                        <div className="space-y-6">
                                            {/* Overview */}
                                            <div className="space-y-4">
                                                <h3 className="text-lg font-semibold text-zinc-200">Sinopsis</h3>
                                                <p className="text-zinc-400 leading-relaxed text-sm">
                                                    {mediaDetails.overview || "No hay sinopsis disponible para este título."}
                                                </p>
                                            </div>

                                            {/* Cast (Horizontal Scroll) */}
                                            {mediaDetails.cast?.length > 0 && (
                                                <div className="space-y-4 pt-4">
                                                    <h3 className="text-lg font-semibold text-zinc-200">Reparto Principal</h3>
                                                    <div className="flex overflow-x-auto gap-4 pb-4 snap-x hide-scrollbar">
                                                        {mediaDetails.cast.map((actor: { id: number, name: string, character: string, profile_path: string }, i: number) => (
                                                            <div
                                                                key={i}
                                                                onClick={() => handleActorClick(actor.id)}
                                                                className="flex-shrink-0 w-[100px] flex flex-col items-center gap-3 cursor-pointer group snap-start"
                                                            >
                                                                {actor.profile_path ? (
                                                                    <img src={actor.profile_path} className="w-20 h-20 rounded-full object-cover ring-2 ring-zinc-800 group-hover:ring-amber-500 transition-all shadow-lg" alt={actor.name} />
                                                                ) : (
                                                                    <div className="w-20 h-20 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-500 text-2xl font-bold ring-2 ring-zinc-800 group-hover:ring-amber-500 transition-all shadow-lg">
                                                                        {actor.name.charAt(0)}
                                                                    </div>
                                                                )}
                                                                <div className="text-center w-full">
                                                                    <span className="block text-sm font-medium text-zinc-200 line-clamp-1 group-hover:text-amber-400 transition-colors">{actor.name}</span>
                                                                    <span className="block text-xs text-zinc-500 line-clamp-2 leading-tight mt-1">{actor.character || "Actor"}</span>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        <hr className="border-zinc-800/50" />

                                        {/* Acciones: Streams para Películas o Selector para Series */}
                                        {selectedItem.media_type === 'movie' ? (
                                            <div className="space-y-4">
                                                <h3 className="text-lg font-semibold text-zinc-200 flex items-center gap-2">
                                                    <Play className="w-5 h-5 text-amber-500" /> Fuentes Disponibles
                                                </h3>
                                                {renderStreamsList()}
                                            </div>
                                        ) : (
                                            <div className="space-y-6">
                                                <div className="flex items-center justify-between">
                                                    <h3 className="text-lg font-semibold text-zinc-200 flex items-center gap-2">
                                                        <Tv className="w-5 h-5 text-amber-500" /> Episodios
                                                    </h3>
                                                    <select
                                                        value={selectedSeason || ''}
                                                        onChange={(e) => handleSeasonSelect(selectedItem, parseInt(e.target.value))}
                                                        className="bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm rounded-lg focus:ring-amber-500 focus:border-amber-500 block p-2 outline-none"
                                                    >
                                                        {mediaDetails.seasons?.map((s: any) => (
                                                            <option key={s.season_number} value={s.season_number}>
                                                                {s.name} ({s.episode_count} eps)
                                                            </option>
                                                        ))}
                                                    </select>
                                                </div>

                                                {/* Lista de Episodios Si No hay stream activo */}
                                                {!loadingStreams && streams.length === 0 && (
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                        {episodes.map(ep => (
                                                            <div key={ep.id} onClick={() => handleEpisodeSelect(ep.episode_number)} className="bg-zinc-900/50 border border-zinc-800/50 hover:border-amber-500/50 hover:bg-zinc-900 rounded-xl p-3 flex gap-4 cursor-pointer transition-colors group relative">
                                                                <div className="w-24 h-16 shrink-0 bg-zinc-800 rounded-md overflow-hidden relative">
                                                                    {ep.still_path ? <img src={ep.still_path} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" /> : null}
                                                                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                                                        <Play className="w-6 h-6 text-white" />
                                                                    </div>

                                                                    {/* SYNC INDICATORS */}
                                                                    {episodeSyncStatus[ep.episode_number] === 'synced' && (
                                                                        <div className="absolute top-1 right-1 bg-green-500 rounded-full p-1 shadow-lg ring-2 ring-zinc-950">
                                                                            <CheckCircle2 className="w-3 h-3 text-zinc-950" />
                                                                        </div>
                                                                    )}
                                                                    {(episodeSyncStatus[ep.episode_number] === 'pending' || activeDownloads[`${selectedItem.title} S${selectedSeason}E${ep.episode_number}`]) && (
                                                                        <div className="absolute top-1 right-1 bg-amber-500 rounded-full p-1 shadow-lg ring-2 ring-zinc-950 animate-pulse">
                                                                            <Activity className="w-3 h-3 text-zinc-950" />
                                                                        </div>
                                                                    )}
                                                                </div>
                                                                <div className="flex-1 min-w-0 py-1">
                                                                    <div className="flex items-center gap-2">
                                                                        <h4 className="text-sm font-medium text-zinc-200 line-clamp-1">{ep.episode_number}. {ep.name}</h4>
                                                                        {episodeSyncStatus[ep.episode_number] === 'synced' && (
                                                                            <span className="text-[9px] font-black text-green-500 uppercase tracking-widest bg-green-500/10 px-1.5 py-0.5 rounded border border-green-500/20">En Plex</span>
                                                                        )}
                                                                        <button
                                                                            onClick={(e) => { e.stopPropagation(); handleOpenManualLink(selectedSeason, ep.episode_number); }}
                                                                            className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-amber-500 transition-colors border border-zinc-700/50"
                                                                            title="Vincular manualmente"
                                                                        >
                                                                            <LinkIcon className="w-3 h-3" />
                                                                        </button>
                                                                    </div>
                                                                    <p className="text-xs text-zinc-500 mt-1 line-clamp-1">{ep.overview || "Sin descripción."}</p>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}

                                                {/* Streams selection for the picked episode */}
                                                {(loadingStreams || streams.length > 0) && (
                                                    <div className="mt-6 bg-zinc-900/30 p-4 rounded-xl border border-zinc-800/50">
                                                        <div className="flex justify-between items-center mb-4">
                                                            <h4 className="font-medium text-amber-400">Fuentes para: Temporada {selectedSeason} Episodio {selectedItem?.current_episode}</h4>
                                                            <button onClick={() => setStreams([])} className="text-xs text-zinc-500 hover:text-zinc-300">Volver a episodios</button>
                                                        </div>
                                                        {renderStreamsList()}
                                                    </div>
                                                )}

                                            </div>
                                        )}

                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Library Structure Modal */}
            {
                showLibStruct && libStructItem && (
                    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
                        <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
                            <div className="p-5 border-b border-zinc-900 flex justify-between items-center bg-zinc-900/30">
                                <div>
                                    <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
                                        <TerminalSquare className="w-5 h-5 text-amber-500" />
                                        Estructura Local: {libStructItem.name}
                                    </h2>
                                    <p className="text-xs text-zinc-500 mt-1">Explorando symlinks en el disco de Plex</p>
                                </div>
                                <div className="flex items-center gap-3">
                                    {libStructDetails && (
                                        <button
                                            onClick={async () => {
                                                const itemForDetails = {
                                                    id: libStructItem.tmdb_id,
                                                    title: libStructDetails.title || libStructDetails.name || libStructItem.name,
                                                    original_title: libStructDetails.original_title,
                                                    year: libStructDetails.year || "",
                                                    media_type: libStructItem.media_type,
                                                    poster_path: libStructDetails.poster_path
                                                };
                                                setSelectedItem(itemForDetails);
                                                setMediaDetails(libStructDetails);
                                                setShowLibStruct(false);
                                                setShowDetails(true);

                                                // Check base symlink existence
                                                const exists = await checkSymlink(itemForDetails);
                                                setSymlinkExists(exists);

                                                // Si es serie, cargar la primera temporada
                                                if (libStructItem.media_type === 'tv' && libStructDetails.seasons?.length > 0) {
                                                    handleSeasonSelect(itemForDetails, libStructDetails.seasons[0].season_number);
                                                }
                                            }}
                                            className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition-all shadow-lg shadow-amber-500/20"
                                        >
                                            <Plus className="w-4 h-4" /> Agregar Episodios
                                        </button>
                                    )}
                                    
                                    {/* Botones de eliminación en masa */}
                                    <div className="flex items-center gap-2">
                                        {libStructItem.media_type === 'tv' ? (
                                            // Opciones para series
                                            <>
                                                <div className="relative group">
                                                    <button className="px-3 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 font-bold rounded-xl text-xs border border-red-500/30 transition-all flex items-center gap-2">
                                                        <Trash2 className="w-3 h-3" /> Borrar...
                                                    </button>
                                                    <div className="absolute right-0 top-full mt-1 w-56 bg-zinc-900 border border-zinc-800 rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                                                        <div className="p-3 space-y-2">
                                                            {libStructDetails.seasons?.map((season: any) => (
                                                                <button
                                                                    key={season.season_number}
                                                                    onClick={() => deleteEntireSeason(season.season_number)}
                                                                    className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                                                >
                                                                    Borrar Temporada {season.season_number}
                                                                </button>
                                                            ))}
                                                            <div className="border-t border-zinc-800 my-2"></div>
                                                            <button
                                                                onClick={() => deleteEntireSeries()}
                                                                className="w-full text-left px-3 py-1.5 text-xs text-red-600 hover:bg-red-500/20 font-bold rounded transition-colors"
                                                            >
                                                                🔥 Borrar Serie Completa
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </>
                                        ) : (
                                            // Opción para películas
                                            <button
                                                onClick={() => deleteEntireMovie()}
                                                className="px-3 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 font-bold rounded-xl text-xs border border-red-500/30 transition-all flex items-center gap-2"
                                            >
                                                <Trash2 className="w-3 h-3" /> Borrar Película
                                            </button>
                                        )}
                                    </div>
                                    
                                    <button
                                        onClick={() => setShowLibStruct(false)}
                                        className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 hover:text-white transition-colors"
                                    >
                                        <X className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>

                            <div className="flex-1 overflow-y-auto p-6 bg-zinc-950/50">
                                {loadingStruct ? (
                                    <div className="flex flex-col items-center justify-center h-40 space-y-4">
                                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500"></div>
                                        <p className="text-zinc-500 text-sm">Escaneando directorio...</p>
                                    </div>
                                ) : libStructData.length === 0 ? (
                                    <div className="text-center text-zinc-600 py-10 italic">
                                        No se encontraron archivos o directorios.
                                    </div>
                                ) : (
                                    <div className="space-y-2 font-mono text-sm">
                                        {libStructData.map((node, i) => (
                                            <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${node.type === 'directory' ? 'bg-zinc-900/80 border-zinc-800' : 'bg-zinc-900/30 border-zinc-800/50 hover:border-zinc-700'} transition-colors`}>
                                                <div 
                                                    className="flex items-center gap-3 overflow-hidden flex-1 cursor-pointer" 
                                                    onClick={() => node.type === 'file' && getSymlinkInfo(node.full_path)}
                                                >
                                                    {node.type === 'directory' ? (
                                                        <div className="w-6 h-6 flex items-center justify-center rounded bg-amber-500/10">
                                                            <span className="text-amber-500 text-lg">📁</span>
                                                        </div>
                                                    ) : (
                                                        <div className="w-6 h-6 flex items-center justify-center rounded bg-blue-500/10">
                                                            <span className="text-blue-500 text-lg">📄</span>
                                                        </div>
                                                    )}
                                                    <span className={`truncate ${node.type === 'directory' ? 'text-zinc-300 font-semibold' : 'text-zinc-400'}`}>
                                                        {node.path}
                                                    </span>
                                                    {node.type === 'file' && node.is_symlink && (
                                                        <span className="px-2 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/20 uppercase tracking-widest ml-2 shrink-0">
                                                            Symlink
                                                        </span>
                                                    )}
                                                </div>

                                                {node.type === 'file' && (
                                                    <div className="flex items-center gap-2 shrink-0 ml-4">
                                                        {symlinkStatuses[node.full_path] === 'testing' ? (
                                                            <span className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-zinc-800 text-zinc-400 text-xs">
                                                                <div className="w-3 h-3 border-2 border-zinc-500 border-t-transparent rounded-full animate-spin"></div> Probando
                                                            </span>
                                                        ) : symlinkStatuses[node.full_path] === 'alive' ? (
                                                            <span className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-green-500/10 text-green-500 border border-green-500/20 text-xs font-semibold">
                                                                <CheckCircle2 className="w-3.5 h-3.5" /> Vivo
                                                            </span>
                                                        ) : symlinkStatuses[node.full_path] === 'dead' ? (
                                                            <span className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-red-500/10 text-red-500 border border-red-500/20 text-xs font-semibold">
                                                                <XCircle className="w-3.5 h-3.5" /> Roto
                                                            </span>
                                                        ) : (
                                                            <button
                                                                onClick={() => testSymlink(node.full_path)}
                                                                className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-md text-xs transition-colors border border-zinc-700"
                                                            >
                                                                Probar Enlace
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => deleteSymlink(node.full_path)}
                                                            title="Eliminar archivo"
                                                            className="p-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-md transition-colors border border-red-500/20 ml-1"
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Symlink Info Modal */}
            {
                selectedSymlinkInfo && (
                    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
                        <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl">
                            <div className="p-5 border-b border-zinc-900 flex justify-between items-center bg-zinc-900/30">
                                <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
                                    <Activity className="w-5 h-5 text-purple-500" />
                                    Detalles del Symlink
                                </h2>
                                <button
                                    onClick={() => setSelectedSymlinkInfo(null)}
                                    className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 hover:text-white transition-colors"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className="p-6 space-y-4">
                                {/* Estado del Symlink */}
                                <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-900/50 border border-zinc-800">
                                    <span className="text-sm font-semibold text-zinc-400">Estado</span>
                                    {selectedSymlinkInfo.is_symlink ? (
                                        selectedSymlinkInfo.is_alive ? (
                                            <span className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-green-500/10 text-green-500 border border-green-500/20 text-sm font-semibold">
                                                <CheckCircle2 className="w-4 h-4" /> Symlink Activo
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-red-500/10 text-red-500 border border-red-500/20 text-sm font-semibold">
                                                <XCircle className="w-4 h-4" /> Symlink Roto
                                            </span>
                                        )
                                    ) : (
                                        <span className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-blue-500/10 text-blue-500 border border-blue-500/20 text-sm font-semibold">
                                            <FileText className="w-4 h-4" /> Archivo Normal
                                        </span>
                                    )}
                                </div>

                                {/* Nombre en Plex (Convertido) */}
                                <div className="space-y-2">
                                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Nombre en Plex (Formato Convertido)</label>
                                    <div className="p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                                        <p className="font-mono text-sm text-emerald-400 break-all">
                                            {selectedSymlinkInfo.symlink_name}
                                        </p>
                                    </div>
                                </div>

                                {/* Nombre Original */}
                                {selectedSymlinkInfo.is_symlink && (
                                    <div className="space-y-2">
                                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Nombre Original (Archivo de TorBox)</label>
                                        <div className="p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
                                            <p className="font-mono text-sm text-amber-400 break-all">
                                                {selectedSymlinkInfo.original_name}
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* Ruta Completa */}
                                <div className="space-y-2">
                                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Ruta Completa del {selectedSymlinkInfo.is_symlink ? 'Origen' : 'Archivo'}</label>
                                    <div className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-800">
                                        <p className="font-mono text-xs text-zinc-500 break-all">
                                            {selectedSymlinkInfo.target_path}
                                        </p>
                                    </div>
                                </div>

                                {/* Comparación Visual */}
                                {selectedSymlinkInfo.is_symlink && selectedSymlinkInfo.original_name !== selectedSymlinkInfo.symlink_name && (
                                    <div className="p-4 rounded-lg bg-purple-500/5 border border-purple-500/20">
                                        <h3 className="text-sm font-semibold text-purple-400 mb-2 flex items-center gap-2">
                                            <Zap className="w-4 h-4" /> Conversión Aplicada
                                        </h3>
                                        <div className="space-y-2 text-xs text-zinc-400">
                                            <div className="flex items-center gap-2">
                                                <span className="text-zinc-500">De:</span>
                                                <span className="font-mono text-amber-400">{selectedSymlinkInfo.original_name}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-zinc-500">A:</span>
                                                <span className="font-mono text-emerald-400">{selectedSymlinkInfo.symlink_name}</span>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )
            }

            {
                showTorBoxBrowser && (
                    <TorBoxBrowser
                        apiBase={API_BASE}
                        onClose={() => { setShowTorBoxBrowser(false); setBrowsingJob(null); }}
                        onSelect={handleManualLink}
                    />
                )
            }
            {/* Global Notification Banner */}
            {globalNotification && (
                <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] animate-in slide-in-from-top duration-300">
                    <div className={`px-6 py-3 rounded-full border shadow-2xl flex items-center gap-3 backdrop-blur-md ${globalNotification.type === 'success'
                        ? 'bg-green-500/20 border-green-500/30 text-green-400'
                        : 'bg-red-500/20 border-red-500/30 text-red-400'
                        }`}>
                        {globalNotification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <Activity className="w-5 h-5" />}
                        <span className="text-sm font-semibold tracking-wide">{globalNotification.message}</span>
                    </div>
                </div>
            )}

            {/* Person Details Modal */}
            {selectedPerson && (
                <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-4xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh] relative">
                        <div className="p-6 border-b border-zinc-900 flex justify-between items-start gap-4 relative z-20">
                            <div className="flex gap-6">
                                {selectedPerson.profile_path ? (
                                    <img src={`https://image.tmdb.org/t/p/w300${selectedPerson.profile_path}`} className="w-28 h-28 rounded-full object-cover shadow-2xl ring-4 ring-zinc-800" alt={selectedPerson.name} />
                                ) : (
                                    <div className="w-28 h-28 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-500 text-3xl font-bold ring-4 ring-zinc-800">
                                        {selectedPerson.name.charAt(0)}
                                    </div>
                                )}
                                <div className="mt-2 flex flex-col justify-center">
                                    <h2 className="text-3xl font-bold text-zinc-100 drop-shadow-md">
                                        {selectedPerson.name}
                                    </h2>
                                    <div className="flex items-center gap-3 mt-2 text-sm text-zinc-400 font-medium">
                                        <span>{selectedPerson.known_for_department}</span>
                                        {selectedPerson.birthday && (
                                            <>
                                                <span>•</span>
                                                <span>{selectedPerson.birthday}</span>
                                            </>
                                        )}
                                        {selectedPerson.place_of_birth && (
                                            <>
                                                <span>•</span>
                                                <span>{selectedPerson.place_of_birth}</span>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => setSelectedPerson(null)}
                                className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 hover:text-white transition-colors cursor-pointer z-30"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="overflow-y-auto flex-1 bg-zinc-950 p-6 space-y-8">
                            {personDetailsLoading ? (
                                <div className="flex flex-col items-center justify-center py-20">
                                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500 mb-4"></div>
                                    <p className="text-zinc-500 text-sm">Cargando perfil...</p>
                                </div>
                            ) : (
                                <>
                                    {selectedPerson.biography && (
                                        <div className="space-y-4">
                                            <h3 className="text-lg font-semibold text-zinc-200">Biografía</h3>
                                            <p className="text-zinc-400 leading-relaxed text-sm whitespace-pre-wrap">
                                                {selectedPerson.biography}
                                            </p>
                                        </div>
                                    )}

                                    <div className="space-y-4">
                                        <h3 className="text-lg font-semibold text-zinc-200">Conocido por</h3>
                                        {personCredits.length > 0 ? (
                                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                                                {personCredits.map((credit, i) => (
                                                    <div
                                                        key={`${credit.id}-${i}`}
                                                        onClick={() => {
                                                            setSelectedPerson(null);
                                                            handleSelect({
                                                                id: credit.id,
                                                                title: credit.title || credit.name,
                                                                year: credit.year,
                                                                media_type: credit.media_type,
                                                                poster_path: credit.poster_path ? `https://image.tmdb.org/t/p/w200${credit.poster_path}` : null,
                                                                vote_average: credit.vote_average
                                                            });
                                                        }}
                                                        className="group relative flex flex-col gap-2 cursor-pointer bg-zinc-900/30 p-2 rounded-xl border border-zinc-800/50 hover:border-amber-500/50 hover:bg-zinc-900 transition-colors"
                                                    >
                                                        <div className="relative aspect-[2/3] rounded-lg overflow-hidden bg-zinc-800">
                                                            {credit.poster_path ? (
                                                                <img src={`https://image.tmdb.org/t/p/w200${credit.poster_path}`} alt={credit.title || credit.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                                                            ) : (
                                                                <div className="w-full h-full flex items-center justify-center text-zinc-600 text-xs text-center p-2">Sin Poster</div>
                                                            )}
                                                        </div>
                                                        <div className="px-1">
                                                            <h4 className="font-medium text-xs text-zinc-200 line-clamp-1 group-hover:text-amber-400">{credit.title || credit.name}</h4>
                                                            <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 mt-0.5">
                                                                {credit.media_type === 'movie' ? <Film className="w-2.5 h-2.5" /> : <Tv className="w-2.5 h-2.5" />}
                                                                <span>{(credit.release_date || credit.first_air_date || "").split("-")[0] || 'N/A'}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="text-zinc-500 text-sm italic">No se encontraron créditos destacados.</p>
                                        )}
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}

        </div >
    )
}
