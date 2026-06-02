let _cachedClusters = [];
let _dupCountByServerUuid = new Map();
let _cctvCards = new Map();
let _cctvLayoutKey = '';
let _cctvStreams = new Map();
let _appDefaultsCache = new Map();
let _appStatusCache = new Map();
let _draggingUuid = null;
let _dragInit = false;
let _dragPlaceholder = null;

const CLUSTER_ORDER_STORAGE_KEY = 'orchestrator.clusterOrder';
