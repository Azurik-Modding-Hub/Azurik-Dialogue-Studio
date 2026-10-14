'use strict';

const $ = id => document.getElementById(id);
// Native save dialogs are used for exports; no browser-only download links.
function exportButton(parent, id, label, action) {
  const button = document.createElement('button'); button.id = id;
  button.dataset.i18n = label; button.textContent = label;
  button.addEventListener('click', () => task(action)); parent.append(button);
}
const originalTitle = $('textWorkspace').querySelector('article .preview-title');
originalTitle.removeAttribute('data-i18n');
originalTitle.replaceChildren(Object.assign(document.createElement('span'), {textContent: 'Panneau original'}));
originalTitle.firstElementChild.dataset.i18n = 'original';
exportButton(originalTitle, 'downloadOriginalText', 'savePng', () => download('png', false));
exportButton($('previewChip').parentElement, 'downloadEditedText', 'savePng', () => download('png', true));
exportButton($('applyButton').parentElement, 'downloadTxt', 'saveTxt', () => download('txt', true));
for (const [id, label, kind] of [['importTextFile', 'importTxt', 'txt'], ['importPanelImage', 'importPng', 'image']]) {
  exportButton($('applyButton').parentElement, id, label, async () => {
    if (!discardDraft()) return;
    await renderProject(await api('choose_text_file', language, selected, kind));
    toast(t('applied'));
  });
}
exportButton($('originalAudio').parentElement, 'downloadOriginalVoice', 'saveWav', () => download('voice', false));
exportButton($('editedAudio').parentElement, 'downloadEditedVoice', 'saveWav', () => download('voice', true));
const voiceSettings = document.createElement('section'); voiceSettings.className = 'voice-settings';
const gainLabel = document.createElement('label'); gainLabel.dataset.i18n = 'voiceGain';
const gainInput = document.createElement('input'); gainInput.type = 'number'; gainInput.id = 'voiceGain';
gainInput.min = '-12'; gainInput.max = '12'; gainInput.step = '0.5'; gainInput.value = '0';
const startLabel = document.createElement('label'); startLabel.dataset.i18n = 'voiceStart';
const startInput = document.createElement('input'); startInput.type = 'number'; startInput.id = 'voiceStart';
startInput.min = '0'; startInput.max = '600'; startInput.step = '0.01'; startInput.value = '0';
voiceSettings.append(gainLabel, gainInput, startLabel, startInput);
exportButton(voiceSettings, 'applyVoiceOptions', 'applyVoiceSettings', async () => {
  await renderProject(await api('apply_voice_options', language, selected,
    {gainDb: Number($('voiceGain').value), trimStartSeconds: Number($('voiceStart').value)}));
  toast(t('applied'));
});
const voiceSettingsNote = document.createElement('p'); voiceSettingsNote.dataset.i18n = 'voiceSettingsNote';
voiceSettings.append(voiceSettingsNote); $('voiceLimits').before(voiceSettings);
const filePanel = document.querySelector('.drop-panel');
filePanel.append(document.createElement('hr'));
for (const [action, label] of [['downloadTexts', 'saveAllText'], ['downloadVoices', 'saveAllVoices']]) {
  const button = document.createElement('button'); button.dataset.action = action; button.dataset.i18n = label;
  filePanel.append(button);
}
const words = {
  fr: {
    save: 'Enregistrer', export: 'Exporter le mod', file: 'Fichier', edit: 'Édition',
    openDump: 'Ouvrir un dump', openIso: 'Ouvrir une ISO', openProject: 'Ouvrir un projet',
    saveProject: 'Enregistrer le projet · Ctrl+S', exportIso: 'Construire une nouvelle ISO',
    undo: 'Annuler · Ctrl+Z', redo: 'Rétablir · Ctrl+Maj+Z', reset: 'Restaurer tous les originaux',
    help: 'Aide et raccourcis', offline: 'Local · Aucun service payant', library: 'BIBLIOTHÈQUE DU JEU',
    gameLanguage: 'Langue du jeu', texts: 'Textes', voices: 'Voix', protected: 'Originaux protégés',
    restore: 'Restaurer cet élément', welcome: 'Donnez une nouvelle voix à Perathia',
    welcomeText: 'Ouvrez votre dump ou votre ISO. Modifiez les panneaux de dialogue et importez vos enregistrements WAV pour remplacer les voix du jeu.',
    welcomeSafety: 'Les modifications sont exportées dans de nouveaux fichiers. Votre source reste intacte.',
    original: 'Panneau original', preview: 'Votre aperçu', replacementText: 'Texte de remplacement',
    bitmapNote: 'Un texte rédigé conserve le cadre original. Un PNG remplace le panneau entier à sa résolution native.',
    refreshPreview: 'Actualiser l’aperçu', apply: 'Appliquer le texte',
    voiceDescription: 'Importez votre enregistrement pour remplacer cette voix dans le jeu.',
    originalVoice: 'Voix originale', replacementVoice: 'Votre voix', loadOriginal: 'Charger la préécoute',
    importWav: 'Importer un enregistrement WAV', listenReplacement: 'Écouter le remplacement',
    inspector: 'INSPECTEUR', textStyle: 'Style du texte', font: 'Police', size: 'Taille', color: 'Couleur',
    alignment: 'Alignement', textArea: 'Zone d’écriture', project: 'Projet', changedTexts: 'Textes modifiés',
    changedVoices: 'Voix remplacées', formatNote: 'Banques originales EN / FR / DE. Chaque remplacement conserve ses références dans le jeu.',
    exportProgress: 'Export en cours', all: 'Toutes les catégories', panels: 'Panneaux de dialogue',
    empty: 'Aucune ressource trouvée.', ready: 'Prêt', loading: 'Chargement…', noSource: 'Ouvrez votre jeu pour commencer',
    noReplacement: 'Aucun remplacement', saved: 'Enregistré', unsaved: 'Non enregistré',
    originalChip: 'ORIGINAL', previewChip: 'APERÇU', appliedChip: 'APPLIQUÉ', close: 'Fermer',
    search: 'Rechercher une ressource…', placeholder: 'Saisissez votre texte ici. Le texte original est visible dans l’image au-dessus.',
    textKind: 'TEXTES DU JEU', voiceKind: 'VOIX DU JEU', title: 'Vos dialogues, votre voix',
    resource: 'Ressource', bank: 'Banque', dimensions: 'Dimensions', encoding: 'Format', levels: 'Niveaux de détail',
    duration: 'Durée maximale', channels: 'Canaux', frequency: 'Fréquence', category: 'Catégorie',
    applied: 'Modification appliquée au projet.', previewReady: 'Aperçu actualisé. Cliquez sur Appliquer pour conserver ce texte.',
    voiceLoaded: 'Préécoute disponible.', nothing: 'Appliquez une modification avant d’exporter.',
    discardDraft: 'Le texte saisi n’a pas été appliqué. Abandonner cette saisie ?',
    exportDone: 'Export terminé et vérifié.', exportError: 'L’export a été arrêté.',
    limits: 'WAV PCM mono ou stéréo. Durée maximale : {duration}. Conversion locale au format du jeu ; une voix plus courte est complétée par du silence.',
    characters: '{count} caractères', changes: '{count} modification(s)',
    linkedVoice: 'Voix associée', locateVoice: 'Voir la voix associée',
    helpKeys: 'Ctrl+S : enregistrer · Ctrl+F : rechercher · Ctrl+Z : annuler · Ctrl+Maj+Z : rétablir · Ctrl+Entrée : appliquer le texte.',
    helpUndo: 'Dans la zone de texte, Ctrl+Z annule la saisie. Les boutons ↶ / ↷ annulent ou rétablissent les changements déjà appliqués.',
    helpSteps: '1. Ouvrez votre jeu. 2. Choisissez une langue et une ressource. 3. Appliquez votre texte ou importez un WAV. 4. Enregistrez le projet. 5. Exportez les banques ou construisez une nouvelle ISO.',
    helpAudio: 'Le WAV est converti localement. Sa durée ne doit pas dépasser celle de la voix d’origine ; une voix plus courte est complétée par du silence. Aucune voix n’est coupée automatiquement.',
    helpCache: 'Si Xemu affiche encore les anciens fichiers, redémarrez-le complètement sur la nouvelle ISO. Le logiciel ne supprime aucun cache ni fichier de sauvegarde.',
    selection: 'Sélectionnez une ressource dans la bibliothèque.', pendingText: 'Texte en cours de saisie — cliquez sur Appliquer.',
    'Oracles': 'Oracles', "Voix d'Azurik": 'Voix d’Azurik', 'Boîtes de dialogue': 'Boîtes de dialogue',
    'Personnages': 'Personnages', 'Non pris en charge': 'Non pris en charge'
  },
  en: {
    save: 'Save', export: 'Export mod', file: 'File', edit: 'Edit', openDump: 'Open game folder',
    openIso: 'Open ISO', openProject: 'Open project', saveProject: 'Save project · Ctrl+S',
    exportIso: 'Build a new ISO', undo: 'Undo · Ctrl+Z', redo: 'Redo · Ctrl+Shift+Z',
    reset: 'Restore all originals', help: 'Help and shortcuts', offline: 'Local · No paid services',
    library: 'GAME LIBRARY', gameLanguage: 'Game language', texts: 'Text', voices: 'Voices',
    protected: 'Original files protected', restore: 'Restore this resource',
    welcome: 'Give Perathia a new voice',
    welcomeText: 'Open your game folder or ISO. Edit dialogue panels and import WAV recordings to replace game voices.',
    welcomeSafety: 'Changes are exported to new files. Your source stays intact.', original: 'Original panel',
    preview: 'Your preview', replacementText: 'Replacement text',
    bitmapNote: 'Authored text keeps the original frame. A PNG replaces the whole panel at its native resolution.',
    refreshPreview: 'Refresh preview', apply: 'Apply text', voiceDescription: 'Import your recording to replace this voice in the game.',
    originalVoice: 'Original voice', replacementVoice: 'Your voice', loadOriginal: 'Load audio preview',
    importWav: 'Import WAV recording', listenReplacement: 'Preview replacement', inspector: 'INSPECTOR',
    textStyle: 'Text style', font: 'Font', size: 'Size', color: 'Color', alignment: 'Alignment',
    textArea: 'Text region', project: 'Project', changedTexts: 'Edited text panels', changedVoices: 'Replaced voices',
    formatNote: 'Original EN / FR / DE banks. Each replacement keeps its in-game references.',
    exportProgress: 'Export progress', all: 'All categories', panels: 'Dialogue panels', empty: 'No matching resources.',
    ready: 'Ready', loading: 'Loading…', noSource: 'Open your game to begin', noReplacement: 'No replacement',
    saved: 'Saved', unsaved: 'Not saved', originalChip: 'ORIGINAL', previewChip: 'PREVIEW', appliedChip: 'APPLIED',
    close: 'Close', search: 'Search resources…', placeholder: 'Enter your text. The original text is visible in the image above.',
    textKind: 'GAME TEXT', voiceKind: 'GAME VOICES', title: 'Your dialogue, your voice',
    resource: 'Resource', bank: 'Bank', dimensions: 'Dimensions', encoding: 'Format', levels: 'Mip levels',
    duration: 'Maximum duration', channels: 'Channels', frequency: 'Sample rate', category: 'Category',
    applied: 'Change applied to the project.', previewReady: 'Preview updated. Click Apply to keep this text.',
    voiceLoaded: 'Audio preview ready.', nothing: 'Apply a change before exporting.',
    discardDraft: 'Your typed text has not been applied. Discard this draft?', exportDone: 'Export completed and verified.',
    exportError: 'Export stopped.', limits: 'Mono or stereo PCM WAV. Maximum duration: {duration}. Converted locally to the game format; shorter recordings are padded with silence.',
    characters: '{count} characters', changes: '{count} change(s)', linkedVoice: 'Linked voice', locateVoice: 'Show linked voice',
    helpKeys: 'Ctrl+S: save · Ctrl+F: search · Ctrl+Z: undo · Ctrl+Shift+Z: redo · Ctrl+Enter: apply text.',
    helpUndo: 'Inside the text field, Ctrl+Z undoes typing. The ↶ / ↷ buttons undo or redo applied project changes.',
    helpSteps: '1. Open your game. 2. Pick a language and resource. 3. Apply your text or import a WAV. 4. Save the project. 5. Export the banks or build a new ISO.',
    helpAudio: 'WAV audio is converted locally. Its duration must fit the original voice slot; shorter recordings are padded with silence. Audio is never cut automatically.',
    helpCache: 'If Xemu still shows the old files, fully restart it with the new ISO. This software does not delete any cache or save files.',
    selection: 'Choose a resource in the library.', pendingText: 'Text draft — click Apply to keep it.',
    'Oracles': 'Oracles', "Voix d'Azurik": 'Azurik voices', 'Boîtes de dialogue': 'Dialogue boxes',
    'Personnages': 'Characters', 'Non pris en charge': 'Unsupported'
  }
};
let uiLanguage = localStorage.getItem('azurik-dialogue-language') === 'en' ? 'en' : 'fr';
let project = {languages: [], edits: {texts: 0, voices: 0, total: 0}};
let language = 'fr';
let mode = 'texts';
let selected = null;
let loadedDraft = '';
let draft = false;
let request = false;
let exporting = false;
let selectionRevision = 0;
let pollTimer = null;
let toastTimer = null;
let draftSync = Promise.resolve();
let notifiedDraft = false;
const t = (key, values = {}) => {
  let value = words[uiLanguage][key] || key;
  for (const [name, replacement] of Object.entries(values)) value = value.replaceAll('{' + name + '}', String(replacement));
  return value;
};
Object.assign(words.fr, {
  savePng: 'Exporter PNG', saveWav: 'Exporter WAV', saveTxt: 'Exporter votre texte TXT',
  saveAllText: 'Exporter les panneaux · Langue active', saveAllVoices: 'Exporter les voix · Langue active',
  downloadDone: 'Fichier enregistré : ', duration: 'Durée originale', importedDuration: 'Votre enregistrement',
  limits: 'Import WAV PCM mono ou stéréo, jusqu’à 10 minutes et 128 Mo. La durée originale ({duration}) peut être dépassée : la banque est reconstruite, sans couper ni accélérer votre voix.',
  helpAudio: 'Le WAV est converti localement et la ressource est adaptée à sa durée. Aucun enregistrement n’est coupé ni accéléré. Une très courte fin silencieuse complète le dernier bloc du format Xbox.',
  helpDownloads: 'Les boutons Exporter PNG / WAV enregistrent la ressource choisie. Votre texte rédigé est aussi disponible en TXT. Fichier → Exporter les panneaux / voix crée une bibliothèque triée pour la langue active.'
});
Object.assign(words.fr, {voiceGain: 'Volume · gain en dB', voiceStart: 'Début à lire · secondes',
  importTxt: 'Importer un texte TXT', importPng: 'Remplacer le panneau PNG',
  applyVoiceSettings: 'Appliquer les réglages audio',
  voiceSettingsNote: 'Le gain positif utilise un limiteur. Un début supérieur à 0 retire cette partie de l’enregistrement : vérifiez votre préécoute pour conserver toute la phrase.'});
Object.assign(words.en, {
  savePng: 'Export PNG', saveWav: 'Export WAV', saveTxt: 'Export your text as TXT',
  saveAllText: 'Export panels · Active language', saveAllVoices: 'Export voices · Active language',
  downloadDone: 'File saved: ', duration: 'Original duration', importedDuration: 'Your recording',
  limits: 'Mono or stereo PCM WAV, up to 10 minutes and 128 MB. Recordings may exceed the original duration ({duration}): the bank is rebuilt without cutting or speeding up your voice.',
  helpAudio: 'WAV audio is converted locally and the resource is resized to fit. Recordings are never cut or sped up. A very short silent tail completes the final Xbox audio block.',
  helpDownloads: 'Export PNG / WAV saves the selected resource. Your authored text can also be saved as TXT. File → Export panels / voices creates a sorted library for the active language.'
});
Object.assign(words.en, {voiceGain: 'Volume · gain in dB', voiceStart: 'Playback start · seconds',
  importTxt: 'Import text TXT', importPng: 'Replace panel PNG',
  applyVoiceSettings: 'Apply audio settings',
  voiceSettingsNote: 'Positive gain uses a limiter. A start greater than 0 removes that part of the recording: preview it to keep the complete spoken line.'});
const helpDownload = document.createElement('p'); helpDownload.dataset.i18n = 'helpDownloads';
$('closeHelp').before(helpDownload);
const bank = () => project.languages.find(item => item.id === language);
const resources = () => bank()?.[mode === 'texts' ? 'dialogues' : 'voices'] || [];
const keyOf = row => mode === 'texts' ? row.resource : row.key;
const selectedRow = () => resources().find(item => keyOf(item) === selected);
const shortName = key => key.split('/').at(-1).replace(/\.tif$/i, '');
const seconds = value => Number(value || 0).toLocaleString(uiLanguage === 'fr' ? 'fr-FR' : 'en-GB', {maximumFractionDigits: 2}) + ' s';

function status(message) { $('status').textContent = message; }
function toast(message, error = false) {
  const element = $('toast');
  element.textContent = message;
  element.classList.toggle('error', error);
  element.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove('visible'), error ? 7000 : 4000);
  status(message);
}
async function api(method, ...args) {
  if (!window.pywebview?.api) throw new Error(uiLanguage === 'fr' ? 'Le lien avec le logiciel est en cours de chargement.' : 'The application bridge is still loading.');
  const result = await window.pywebview.api[method](...args);
  if (!result || result.ok !== true) throw new Error(result?.error || 'Application error');
  return result.data;
}
async function task(callback) {
  if (request || exporting) return;
  request = true;
  document.body.classList.add('busy');
  status(t('loading'));
  try { await draftSync; await callback(); }
  catch (error) { toast(error.message, true); }
  finally { request = false; document.body.classList.remove('busy'); refreshButtons(); }
}
function notifyDraft(active) {
  if (notifiedDraft === active || !window.pywebview?.api) return;
  notifiedDraft = active;
  draftSync = draftSync.then(() => api('set_draft', active)).catch(error => toast(error.message, true));
}
function discardDraft() {
  if (!draft) return true;
  if (!window.confirm(t('discardDraft'))) return false;
  draft = false; notifyDraft(false); return true;
}
function renderMetadata(entries) {
  $('metadata').replaceChildren();
  for (const [label, value] of entries) {
    if (value === undefined || value === null || value === '') continue;
    const dt = document.createElement('dt'); dt.textContent = label;
    const dd = document.createElement('dd'); dd.textContent = String(value); dd.title = String(value);
    $('metadata').append(dt, dd);
  }
}
function refreshButtons() {
  const hasSource = project.languages.length > 0;
  const row = selectedRow();
  $('saveButton').disabled = !hasSource;
  $('exportButton').disabled = !project.edits.total;
  $('undoButton').disabled = !project.canUndo;
  $('redoButton').disabled = !project.canRedo;
  $('restoreButton').disabled = !row?.modified;
  $('applyButton').disabled = !row || !$('newText').value.trim();
  $('previewButton').disabled = !row;
  $('importVoiceButton').disabled = !row?.editable;
  $('loadOriginalVoice').disabled = !row?.editable;
  $('loadEditedVoice').disabled = !row?.modified;
  $('gameLanguage').disabled = !hasSource;
  for (const id of ['downloadOriginalText', 'downloadEditedText', 'downloadOriginalVoice']) $(id).disabled = !row;
  $('downloadEditedVoice').disabled = !row?.modified;
  $('downloadTxt').disabled = !row?.modified || row.kind === 'image';
  $('importTextFile').disabled = !row; $('importPanelImage').disabled = !row;
  for (const id of ['voiceGain', 'voiceStart', 'applyVoiceOptions']) $(id).disabled = !row?.modified;
  for (const element of document.querySelectorAll('[data-action]')) {
    if (element.dataset.action === 'undo') element.disabled = !project.canUndo;
    if (element.dataset.action === 'redo') element.disabled = !project.canRedo;
    if (element.dataset.action === 'reset') element.disabled = !project.edits.total;
    if (element.dataset.action === 'saveProject') element.disabled = !hasSource;
    if (['export', 'exportIso'].includes(element.dataset.action)) element.disabled = !project.edits.total;
    if (['downloadTexts', 'downloadVoices'].includes(element.dataset.action)) element.disabled = !hasSource;
  }
  $('saveStatus').textContent = t('changes', {count: project.edits.total}) + (hasSource ? ' · ' + t(project.dirty ? 'unsaved' : 'saved') : '');
}
function populateCategories() {
  const previous = $('category').value;
  const categories = mode === 'voices' ? [...new Set(resources().map(item => item.category))] : [];
  $('category').replaceChildren(new Option(t('all'), 'all'));
  for (const category of categories) $('category').add(new Option(t(category), category));
  $('category').value = categories.includes(previous) ? previous : 'all';
}
function renderList() {
  const needle = $('search').value.trim().toLocaleLowerCase();
  const category = $('category').value;
  const rows = resources().filter(item => (category === 'all' || item.category === category) &&
    (keyOf(item) + ' ' + (item.category || '') + ' ' + (item.text || '')).toLocaleLowerCase().includes(needle));
  const fragment = document.createDocumentFragment();
  for (const row of rows) {
    const button = document.createElement('button');
    const key = keyOf(row);
    button.className = 'resource-row' + (selected === key ? ' active' : '');
    button.title = key;
    button.setAttribute('aria-pressed', String(selected === key));
    const name = document.createElement('strong'); name.textContent = shortName(key);
    const detail = document.createElement('small');
    detail.textContent = mode === 'texts' ? row.width + ' × ' + row.height + ' · ' + row.format :
      t(row.category) + ' · ' + seconds(row.duration);
    const badge = document.createElement('span'); badge.textContent = row.modified ? '●' : mode === 'texts' ? '▤' : '♫';
    badge.className = row.modified ? 'modified-dot' : 'resource-symbol';
    const description = document.createElement('div'); description.append(name, detail);
    button.append(badge, description);
    button.addEventListener('click', () => {
      if (selected === key || !discardDraft()) return;
      task(async () => { selected = key; renderList(); await loadSelection(); });
    });
    fragment.append(button);
  }
  if (!rows.length) {
    const empty = document.createElement('p'); empty.className = 'subtle'; empty.textContent = t('empty'); fragment.append(empty);
  }
  $('resourceList').replaceChildren(fragment);
}
function updateDraft() {
  const config = currentOptions();
  draft = JSON.stringify({text: $('newText').value, options: config}) !== loadedDraft;
  notifyDraft(draft);
  $('characterCount').textContent = t('characters', {count: $('newText').value.length});
  $('previewChip').textContent = t(draft ? 'previewChip' : selectedRow()?.modified ? 'appliedChip' : 'originalChip');
  if (draft) status(t('pendingText'));
  refreshButtons();
}
function currentOptions() {
  return {fontFamily: $('fontFamily').value, fontSize: Number($('fontSize').value), color: $('textColor').value,
    align: $('textAlign').value, rect: [0, 1, 2, 3].map(index => Number($('rect' + index).value))};
}
function useOptions(options) {
  $('fontFamily').value = options.fontFamily;
  $('fontSize').value = options.fontSize;
  $('textColor').value = options.color;
  $('textAlign').value = options.align;
  options.rect.forEach((value, index) => $('rect' + index).value = value);
}
function clearAudio() {
  for (const id of ['originalAudio', 'editedAudio']) { $(id).pause(); $(id).removeAttribute('src'); $(id).load(); }
}
async function loadSelection() {
  const revision = ++selectionRevision;
  const row = selectedRow();
  draft = false;
  notifyDraft(false);
  clearAudio();
  $('welcome').hidden = !!row;
  $('textWorkspace').hidden = !row || mode !== 'texts';
  $('voiceWorkspace').hidden = !row || mode !== 'voices';
  $('textSettings').hidden = !row || mode !== 'texts';
  $('selectionKind').textContent = t(mode === 'texts' ? 'textKind' : 'voiceKind');
  $('selectionTitle').textContent = row ? shortName(selected) : t('title');
  if (!row) { renderMetadata([]); refreshButtons(); return; }
  if (mode === 'texts') {
    $('originalPanel').removeAttribute('src'); $('editedPanel').removeAttribute('src');
    const result = await api('preview_text', language, selected);
    if (revision !== selectionRevision) return;
    $('originalPanel').src = result.original; $('editedPanel').src = result.preview;
    $('newText').value = result.text; useOptions(result.options);
    loadedDraft = JSON.stringify({text: result.text, options: currentOptions()});
    updateDraft();
    renderMetadata([[t('resource'), selected], [t('bank'), bank().gamePath],
      [t('dimensions'), row.width + ' × ' + row.height], [t('encoding'), row.format], [t('levels'), row.mipLevels],
      [t('linkedVoice'), row.voiceResource]]);
    if (row.voiceResource && bank().voices.some(item => item.key === row.voiceResource)) {
      const button = document.createElement('button'); button.textContent = t('locateVoice');
      button.addEventListener('click', () => {
        if (!discardDraft()) return;
        task(async () => { mode = 'voices'; selected = row.voiceResource; $('search').value = ''; $('category').value = 'all'; await renderProject(); });
      });
      $('metadata').append(button);
    }
  } else {
    $('voiceTitle').textContent = shortName(selected); $('voiceCategory').textContent = t(row.category);
    $('replacementName').textContent = row.importedName || t('noReplacement');
    $('voiceGain').value = row.options?.gainDb || 0; $('voiceStart').value = row.options?.trimStartSeconds || 0;
    $('voiceLimits').textContent = row.editable ? t('limits', {duration: seconds(row.duration)}) : row.error || t('Non pris en charge');
    renderMetadata([[t('resource'), selected], [t('bank'), bank().gamePath], [t('category'), t(row.category)],
      [t('duration'), seconds(row.duration)], [t('channels'), row.channels === 2 ? 'Stereo' : 'Mono'],
      [t('importedDuration'), row.replacement ? seconds(row.replacement.importDuration) : null],
      [t('frequency'), row.rate + ' Hz'], [t('encoding'), 'Xbox IMA ADPCM']]);
  }
  refreshButtons(); status(t('ready'));
}
async function renderProject(next = project) {
  project = next;
  if (!bank()) language = project.languages[0]?.id || 'fr';
  $('gameLanguage').replaceChildren(...project.languages.map(item => new Option(item.label, item.id)));
  $('gameLanguage').value = language;
  $('sourceTitle').textContent = project.sourcePath ? project.sourcePath.split(/[\\/]/).at(-1) : t('noSource');
  $('sourceTitle').title = project.sourcePath || '';
  $('sourcePath').textContent = project.sourcePath || '—';
  $('textCount').textContent = bank()?.dialogues.length || 0; $('voiceCount').textContent = bank()?.voices.length || 0;
  $('editedTexts').textContent = project.edits.texts; $('editedVoices').textContent = project.edits.voices;
  if (project.version) $('version').textContent = project.version;
  for (const button of document.querySelectorAll('[data-mode]')) button.classList.toggle('active', button.dataset.mode === mode);
  if (!selectedRow()) selected = null;
  populateCategories(); renderList(); await loadSelection();
  $('welcome').querySelectorAll('[data-action]').forEach(element => element.hidden = !!bank());
  if (bank() && !selected) $('welcome').querySelector('[data-i18n="welcomeText"]').textContent = t('selection');
}
function translate() {
  document.documentElement.lang = uiLanguage;
  $('uiLanguage').value = uiLanguage;
  for (const element of document.querySelectorAll('[data-i18n]')) element.textContent = t(element.dataset.i18n);
  $('search').placeholder = t('search'); $('newText').placeholder = t('placeholder');
  $('textAlign').options[0].text = uiLanguage === 'fr' ? 'Centré' : 'Center';
  $('textAlign').options[1].text = uiLanguage === 'fr' ? 'Gauche' : 'Left';
  $('closeHelp').textContent = t('close'); $('closeProgress').textContent = t('close');
  const paragraphs = $('help').querySelectorAll('p');
  ['helpKeys', 'helpUndo', 'helpSteps', 'helpAudio', 'helpCache'].forEach((key, index) => { if (paragraphs[index]) paragraphs[index].textContent = t(key); });
  populateCategories(); renderList(); refreshButtons();
}
async function refreshPreview() {
  const revision = selectionRevision;
  // With no draft, display the applied resource, including imported PNGs.
  const result = draft
    ? await api('preview_text', language, selected, $('newText').value, currentOptions())
    : await api('preview_text', language, selected);
  if (revision !== selectionRevision) return;
  $('editedPanel').src = result.preview; updateDraft(); toast(t('previewReady'));
}
async function applyText() {
  const next = await api('apply_text', language, selected, $('newText').value, currentOptions());
  draft = false; await renderProject(next); toast(t('applied'));
}
async function loadVoice(modified) {
  const revision = selectionRevision;
  const result = await api('preview_voice', language, selected, modified);
  if (revision !== selectionRevision) return;
  const player = $(modified ? 'editedAudio' : 'originalAudio');
  player.preload = 'metadata'; player.src = result.audio; player.load();
  toast(t('voiceLoaded'));
}
async function download(kind, modified) {
  if (draft && modified) {
    await applyText();
  }
  const result = await api('download_resource', kind, language, selected, modified);
  if (result) toast(t('downloadDone') + result.path);
}
async function pollJob() {
  try {
    const job = await api('get_job');
    if (!job) return;
    $('progressBar').value = job.progress; $('progressPercent').textContent = job.progress + ' %';
    $('progressStage').textContent = job.stage;
    if (job.status === 'running') { pollTimer = setTimeout(pollJob, 800); return; }
    exporting = false; $('closeProgress').hidden = false;
    if (job.status === 'error') { $('progressStage').textContent = job.error; toast(job.error, true); }
    else {
      $('progressStage').textContent = t('exportDone') + '\n' + (job.result?.iso || job.result?.destination || '');
      toast(t('exportDone')); project = await api('boot'); refreshButtons();
    }
  } catch (error) {
    exporting = false; $('closeProgress').hidden = false; $('progressStage').textContent = error.message; toast(error.message, true);
  }
}
async function beginExport(method, ...args) {
  if (method !== 'download_library' && !project.edits.total) throw new Error(t('nothing'));
  if (!discardDraft()) return;
  await loadSelection();
  const job = await api(method, ...args);
  if (!job) { status(t('ready')); return; }
  exporting = true; $('closeProgress').hidden = true; $('progressBar').value = 0;
  $('progressPercent').textContent = '0 %'; $('progressStage').textContent = job.stage;
  $('progressDialog').showModal(); clearTimeout(pollTimer); await pollJob();
}
async function dispatch(action) {
  for (const drop of document.querySelectorAll('.drop')) drop.classList.remove('open');
  if (['dump', 'iso', 'openProject', 'undo', 'redo', 'reset'].includes(action) && !discardDraft()) return;
  if (action === 'dump' || action === 'iso') { await renderProject(await api('choose_source', action)); }
  else if (action === 'openProject') { await renderProject(await api('open_project')); }
  else if (action === 'saveProject') {
    // A draft is distinct from an applied change, and must be kept or abandoned explicitly.
    if (draft) { await applyText(); }
    await renderProject(await api('save_project'));
  } else if (action === 'export' || action === 'exportIso') { await beginExport(action === 'export' ? 'export_mod' : 'export_iso'); }
  else if (action === 'downloadTexts' || action === 'downloadVoices') { await beginExport('download_library', action === 'downloadTexts' ? 'text' : 'voice', language); }
  else if (['undo', 'redo', 'reset'].includes(action)) { await renderProject(await api(action)); }
}
for (const element of document.querySelectorAll('[data-action]')) element.addEventListener('click', () => task(() => dispatch(element.dataset.action)));
for (const drop of document.querySelectorAll('.drop')) drop.querySelector(':scope > button').addEventListener('click', () => {
  const opened = drop.classList.contains('open');
  for (const item of document.querySelectorAll('.drop')) item.classList.remove('open');
  drop.classList.toggle('open', !opened);
});
document.addEventListener('click', event => { if (!event.target.closest('.drop')) document.querySelectorAll('.drop').forEach(item => item.classList.remove('open')); });
for (const button of document.querySelectorAll('[data-mode]')) button.addEventListener('click', () => {
  if (mode === button.dataset.mode || !discardDraft()) return;
  task(async () => { mode = button.dataset.mode; selected = null; $('search').value = ''; $('category').value = 'all'; await renderProject(); });
});
$('gameLanguage').addEventListener('change', () => {
  const next = $('gameLanguage').value;
  if (!discardDraft()) { $('gameLanguage').value = language; return; }
  task(async () => { language = next; selected = null; await renderProject(); });
});
$('uiLanguage').addEventListener('change', () => {
  uiLanguage = $('uiLanguage').value; localStorage.setItem('azurik-dialogue-language', uiLanguage); translate();
  if (!draft) task(() => renderProject());
});
$('search').addEventListener('input', renderList); $('category').addEventListener('change', renderList);
for (const id of ['newText', 'fontFamily', 'fontSize', 'textColor', 'textAlign', 'rect0', 'rect1', 'rect2', 'rect3']) $(id).addEventListener('input', updateDraft);
$('previewButton').addEventListener('click', () => task(refreshPreview));
$('applyButton').addEventListener('click', () => task(applyText));
$('saveButton').addEventListener('click', () => task(() => dispatch('saveProject')));
$('exportButton').addEventListener('click', () => task(() => dispatch('export')));
$('undoButton').addEventListener('click', () => task(() => dispatch('undo')));
$('redoButton').addEventListener('click', () => task(() => dispatch('redo')));
$('restoreButton').addEventListener('click', () => {
  if (!discardDraft()) return;
  task(async () => renderProject(await api('restore', mode === 'texts' ? 'text' : 'voice', language, selected)));
});
$('importVoiceButton').addEventListener('click', () => task(async () => { await renderProject(await api('choose_voice', language, selected)); }));
$('loadOriginalVoice').addEventListener('click', () => task(() => loadVoice(false)));
$('loadEditedVoice').addEventListener('click', () => task(() => loadVoice(true)));
$('helpButton').addEventListener('click', () => $('help').showModal());
$('closeHelp').addEventListener('click', () => $('help').close());
$('closeProgress').addEventListener('click', () => { if (!exporting) $('progressDialog').close(); });
$('progressDialog').addEventListener('cancel', event => { if (exporting) event.preventDefault(); });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') document.querySelectorAll('.drop').forEach(item => item.classList.remove('open'));
  if (!event.ctrlKey || event.altKey || event.repeat) return;
  const key = event.key.toLowerCase();
  if (key === 'f') { event.preventDefault(); $('search').focus(); $('search').select(); }
  else if (key === 's') { event.preventDefault(); task(() => dispatch('saveProject')); }
  else if (key === 'enter' && mode === 'texts' && selected && $('newText').value.trim()) { event.preventDefault(); task(applyText); }
  else if (key === 'z' && !event.target.closest('textarea, input, select')) { event.preventDefault(); task(() => dispatch(event.shiftKey ? 'redo' : 'undo')); }
});
let initialized = false;
async function initialize() {
  if (initialized) return;
  initialized = true; translate();
  await task(async () => { await renderProject(await api('boot')); status(t('ready')); });
}
window.addEventListener('pywebviewready', initialize);
if (window.pywebview?.api) initialize();
else { translate(); status(t('loading')); }
