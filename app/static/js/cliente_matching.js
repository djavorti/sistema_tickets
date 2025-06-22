function normalizeText(str) {
    return (str || '')
        .toUpperCase()
        .normalize("NFD").replace(/[\u0300-\u036f]/g, '')
        .replace(/[^A-Z0-9\s]/g, ' ')
        .replace(/\d+/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

const ignoredTokens = new Set([
    'IC', 'SP', 'TIC', 'GST', 'GSM', 'HW', 'SW', 'W08', 'R2LRE', 'CPE', 'CT'
]);

const commonWords = new Set([
    'SAN', 'JUAN', 'GESTION', 'HACIENDA', 'HCDA', 'LA', 'UN', 'PLATAFORMA', 'ABRIL', 'VINCES', 'VI'
]);

function getWords(str) {
    return normalizeText(str)
        .split(/[\s_\-\/]+/)
        .filter(w => w.length >= 2 && !ignoredTokens.has(w));
}

function buildClientKeywordsMap(clienteNames) {
    const map = new Map();
    for (const cliente of clienteNames) {
        const words = getWords(cliente);
        for (const word of words) {
            if (commonWords.has(word)) continue;
            if (!map.has(word)) map.set(word, new Set());
            map.get(word).add(cliente);
        }
    }
    return map;
}

function matchClienteBySede(sedeText, clienteNames) {
    if (!sedeText || !clienteNames?.length) return null;

    const sedeWords = getWords(sedeText);
    const keywordsMap = buildClientKeywordsMap(clienteNames);

    // Early match (seguro): solo si la palabra está al inicio y es única
    for (let i = 0; i < Math.min(3, sedeWords.length); i++) {
        const word = sedeWords[i];
        if (commonWords.has(word)) continue;
        const clients = keywordsMap.get(word);
        if (clients && clients.size === 1) {
            const client = [...clients][0];
            // verificar si hay otra palabra del cliente presente
            const clientWords = getWords(client);
            const intersect = clientWords.filter(w => sedeWords.includes(w));
            if (intersect.length >= 2) {
                return client;
            }
        }
    }

    // Match por score tradicional
    let bestMatch = null;
    let bestScore = 0;

    for (const cliente of clienteNames) {
        const clienteWords = getWords(cliente);
        let score = 0;

        for (let i = 0; i < clienteWords.length; i++) {
            const cWord = clienteWords[i];
            if (commonWords.has(cWord)) continue;

            for (let j = 0; j < sedeWords.length; j++) {
                const sWord = sedeWords[j];

                if (sWord === cWord) {
                    score += (j < 3 ? 10 : 6);
                } else if (sWord.includes(cWord) || cWord.includes(sWord)) {
                    score += (j < 3 ? 5 : 3);
                }
            }
        }

        if (score > bestScore) {
            bestScore = score;
            bestMatch = cliente;
        }
    }

    return bestScore >= 10 ? bestMatch : null;
}