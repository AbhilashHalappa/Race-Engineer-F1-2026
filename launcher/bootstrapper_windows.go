//go:build windows

// Stable V2 external-dependency bootstrapper for Race Engineer.
//
// The executable intentionally does NOT embed Python, Piper voices, Whisper
// weights, Ollama, or the LLM model.  It checks what is already installed and
// asks the user before downloading anything from the Internet.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	mbOK              = 0x00000000
	mbOKCancel        = 0x00000001
	mbYesNo           = 0x00000004
	mbIconError       = 0x00000010
	mbIconQuestion    = 0x00000020
	mbIconWarning     = 0x00000030
	mbIconInformation = 0x00000040
	mbSetForeground   = 0x00010000
	idOK              = 1
	idCancel          = 2
	idYes             = 6
	idNo              = 7
)

var (
	user32      = syscall.NewLazyDLL("user32.dll")
	procMsgBoxW = user32.NewProc("MessageBoxW")
)

type RuntimeConfig struct {
	Schema  int    `json:"schema"`
	Release string `json:"release"`
	Policy  string `json:"policy"`
	Python  struct {
		RequiredMajorMinor string `json:"required_major_minor"`
		DownloadURL        string `json:"download_url"`
		Requirements       string `json:"requirements"`
	} `json:"python"`
	PythonImports []string `json:"python_imports"`
	PiperVoice    struct {
		ModelPath        string `json:"model_path"`
		ConfigPath       string `json:"config_path"`
		ModelURL         string `json:"model_url"`
		ConfigURL        string `json:"config_url"`
		ModelSHA256      string `json:"model_sha256"`
		ApproxDownloadMB int    `json:"approx_download_mb"`
	} `json:"piper_voice"`
	STT struct {
		ModelName        string `json:"model_name"`
		RepoID           string `json:"repo_id"`
		ApproxDownloadMB int    `json:"approx_download_mb"`
	} `json:"stt"`
	LLM struct {
		Runtime     string `json:"runtime"`
		Model       string `json:"model"`
		DownloadURL string `json:"download_url"`
		APIURL      string `json:"api_url"`
		RequiredFor string `json:"required_for"`
	} `json:"llm"`
}

type PythonCommand struct {
	Exe    string
	Prefix []string
}

type Status struct {
	CheckedAtUTC   string   `json:"checked_at_utc"`
	Release        string   `json:"release"`
	Windows        bool     `json:"windows"`
	Python         bool     `json:"python_313"`
	VirtualEnv     bool     `json:"virtual_env"`
	PythonPackages bool     `json:"python_packages"`
	PiperVoice     bool     `json:"piper_voice"`
	STTModel       bool     `json:"stt_model"`
	Ollama         bool     `json:"ollama"`
	LLMModel       bool     `json:"llm_model"`
	FFmpeg         bool     `json:"ffmpeg_optional"`
	CoreReady      bool     `json:"core_ready"`
	MissingFeature []string `json:"missing_features,omitempty"`
	Notes          []string `json:"notes,omitempty"`
}

var logFile *os.File

func logf(format string, args ...any) {
	line := fmt.Sprintf("%s ", time.Now().Format(time.RFC3339)) + fmt.Sprintf(format, args...) + "\r\n"
	if logFile != nil {
		_, _ = io.WriteString(logFile, line)
		_ = logFile.Sync()
	}
}

func message(text, title string, flags uintptr) int {
	pText, _ := syscall.UTF16PtrFromString(text)
	pTitle, _ := syscall.UTF16PtrFromString(title)
	r, _, _ := procMsgBoxW.Call(0, uintptr(unsafe.Pointer(pText)), uintptr(unsafe.Pointer(pTitle)), flags|mbSetForeground)
	return int(r)
}

func askYesNo(text string) bool {
	return message(text, "Race Engineer — Stable V2", mbYesNo|mbIconQuestion) == idYes
}

func fail(text string) int {
	logf("FATAL: %s", text)
	message(text, "Race Engineer — Stable V2", mbOK|mbIconError)
	return 1
}

func openURL(url string) error {
	logf("Opening URL: %s", url)
	return exec.Command("rundll32.exe", "url.dll,FileProtocolHandler", url).Start()
}

func runCapture(exe string, args ...string) (string, error) {
	cmd := exec.Command(exe, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	out, err := cmd.CombinedOutput()
	text := strings.TrimSpace(string(out))
	logf("RUN(hidden): %s %s -> %v | %s", exe, strings.Join(args, " "), err, text)
	return text, err
}

func runInteractive(exe string, args ...string) error {
	logf("RUN(interactive): %s %s", exe, strings.Join(args, " "))
	cmd := exec.Command(exe, args...)
	cmd.Dir, _ = os.Getwd()
	// Do not set HideWindow here: downloads/installations should visibly show
	// their progress rather than looking like the launcher has frozen.
	err := cmd.Run()
	logf("DONE(interactive): %v", err)
	return err
}

func loadConfig(path string) (RuntimeConfig, error) {
	var cfg RuntimeConfig
	raw, err := os.ReadFile(path)
	if err != nil {
		return cfg, err
	}
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return cfg, err
	}
	if cfg.Schema != 1 || cfg.Python.RequiredMajorMinor == "" || cfg.Python.Requirements == "" {
		return cfg, errors.New("unsupported or incomplete runtime_dependencies.json")
	}
	return cfg, nil
}

func versionOf(py PythonCommand) (string, bool) {
	args := append(append([]string{}, py.Prefix...), "-c", "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
	out, err := runCapture(py.Exe, args...)
	if err != nil {
		return "", false
	}
	re := regexp.MustCompile(`(?m)(\d+)\.(\d+)\.(\d+)`)
	m := re.FindStringSubmatch(out)
	if len(m) != 4 {
		return "", false
	}
	return m[0], true
}

func correctPython(py PythonCommand, required string) (string, bool) {
	v, ok := versionOf(py)
	if !ok {
		return v, false
	}
	return v, strings.HasPrefix(v, required+".") || v == required
}

func findSystemPython(required string) (PythonCommand, string, bool) {
	candidates := []PythonCommand{
		{Exe: "py.exe", Prefix: []string{"-" + required}},
		{Exe: "python.exe"},
	}
	for _, py := range candidates {
		if v, ok := correctPython(py, required); ok {
			return py, v, true
		}
	}
	return PythonCommand{}, "", false
}

func ensureVenv(cfg RuntimeConfig, st *Status) (PythonCommand, error) {
	venvExe := filepath.Join(".venv", "Scripts", "python.exe")
	venv := PythonCommand{Exe: venvExe}
	if v, ok := correctPython(venv, cfg.Python.RequiredMajorMinor); ok {
		logf("Existing venv Python ready: %s", v)
		st.Python = true
		st.VirtualEnv = true
		return venv, nil
	}

	systemPy, version, ok := findSystemPython(cfg.Python.RequiredMajorMinor)
	if !ok {
		text := fmt.Sprintf("Python %s is required and was not found.\n\nRaceEngineer.exe does not bundle Python.\n\nOpen the official Python download page now?", cfg.Python.RequiredMajorMinor)
		if askYesNo(text) {
			_ = openURL(cfg.Python.DownloadURL)
			message("Install 64-bit Python "+cfg.Python.RequiredMajorMinor+" and then run RaceEngineer.exe again.", "Race Engineer — Stable V2", mbOK|mbIconInformation)
		}
		return PythonCommand{}, errors.New("required Python not installed")
	}
	st.Python = true
	logf("System Python ready: %s", version)

	if !askYesNo("Race Engineer needs its own local Python environment (.venv).\n\nCreate it now? No application or AI models are bundled into the EXE.") {
		return PythonCommand{}, errors.New("virtual environment creation declined")
	}
	args := append(append([]string{}, systemPy.Prefix...), "-m", "venv", ".venv")
	if err := runInteractive(systemPy.Exe, args...); err != nil {
		return PythonCommand{}, fmt.Errorf("create .venv: %w", err)
	}
	if v, ok := correctPython(venv, cfg.Python.RequiredMajorMinor); !ok {
		return PythonCommand{}, fmt.Errorf("created .venv but Python %s check failed (got %s)", cfg.Python.RequiredMajorMinor, v)
	}
	st.VirtualEnv = true
	return venv, nil
}

func pythonImportsReady(py PythonCommand, imports []string) bool {
	if len(imports) == 0 {
		return true
	}
	code := "import " + strings.Join(imports, ",") + "; print('OK')"
	args := append(append([]string{}, py.Prefix...), "-c", code)
	_, err := runCapture(py.Exe, args...)
	return err == nil
}

func ensurePythonPackages(cfg RuntimeConfig, py PythonCommand, st *Status) error {
	if pythonImportsReady(py, cfg.PythonImports) {
		st.PythonPackages = true
		return nil
	}
	req := cfg.Python.Requirements
	if _, err := os.Stat(req); err != nil {
		return fmt.Errorf("%s is missing", req)
	}
	if !askYesNo("Required Python packages are missing (UI, TTS runtime, audio/HID, serial and STT runtime).\n\nInstall them now from PyPI using requirements.txt?") {
		return errors.New("Python package installation declined")
	}
	args := append(append([]string{}, py.Prefix...), "-m", "pip", "install", "-r", req)
	if err := runInteractive(py.Exe, args...); err != nil {
		return fmt.Errorf("pip install failed: %w", err)
	}
	if !pythonImportsReady(py, cfg.PythonImports) {
		return errors.New("Python packages are still incomplete after pip install")
	}
	st.PythonPackages = true
	return nil
}

func sha256File(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func customVoiceReady() bool {
	// Respect a previously selected custom Piper voice and verify both files
	// exactly the same way src/tts.py will require them at runtime.
	raw, err := os.ReadFile(filepath.Join("settings", "speech.json"))
	if err != nil {
		return false
	}
	var prefs map[string]any
	if json.Unmarshal(raw, &prefs) != nil {
		return false
	}
	v, ok := prefs["model_path"].(string)
	if !ok || strings.TrimSpace(v) == "" {
		return false
	}
	model := strings.TrimSpace(v)
	modelInfo, mErr := os.Stat(model)
	configInfo, cErr := os.Stat(model + ".json")
	return mErr == nil && cErr == nil && modelInfo.Size() > 1024*1024 && configInfo.Size() > 512
}

func defaultVoiceReady(model, config, expectedSHA string) bool {
	modelInfo, mErr := os.Stat(model)
	configInfo, cErr := os.Stat(config)
	if mErr != nil || cErr != nil || modelInfo.Size() <= 1024*1024 || configInfo.Size() <= 512 {
		return false
	}
	if strings.TrimSpace(expectedSHA) == "" {
		return true
	}
	sum, err := sha256File(model)
	return err == nil && strings.EqualFold(sum, expectedSHA)
}

func ensurePiperVoice(cfg RuntimeConfig, py PythonCommand, st *Status) {
	pv := cfg.PiperVoice
	if customVoiceReady() || defaultVoiceReady(pv.ModelPath, pv.ConfigPath, pv.ModelSHA256) {
		st.PiperVoice = true
		return
	}

	prompt := fmt.Sprintf("The default Piper engineer voice is missing or invalid (about %d MB).\n\nDownload it now from the official rhasspy/piper-voices repository?", pv.ApproxDownloadMB)
	if !askYesNo(prompt) {
		st.MissingFeature = append(st.MissingFeature, "Piper TTS voice")
		return
	}
	code := fmt.Sprintf(
		"from pathlib import Path; import urllib.request; "+
			"m=Path(%q); c=Path(%q); m.parent.mkdir(parents=True,exist_ok=True); "+
			"urllib.request.urlretrieve(%q,str(m)); urllib.request.urlretrieve(%q,str(c)); print('Piper voice downloaded')",
		pv.ModelPath, pv.ConfigPath, pv.ModelURL, pv.ConfigURL,
	)
	args := append(append([]string{}, py.Prefix...), "-c", code)
	if err := runInteractive(py.Exe, args...); err != nil {
		st.MissingFeature = append(st.MissingFeature, "Piper TTS voice (download failed)")
		return
	}
	if pv.ModelSHA256 != "" {
		if sum, err := sha256File(pv.ModelPath); err != nil || !strings.EqualFold(sum, pv.ModelSHA256) {
			st.MissingFeature = append(st.MissingFeature, "Piper TTS voice (checksum failed)")
			return
		}
	}
	st.PiperVoice = customVoiceReady() || defaultVoiceReady(pv.ModelPath, pv.ConfigPath, pv.ModelSHA256)
}

func sttCached(py PythonCommand, repoID string) bool {
	code := fmt.Sprintf(
		"import sys; from pathlib import Path; from huggingface_hub import try_to_load_from_cache; "+
			"r=%q; f=['model.bin','config.json','tokenizer.json']; "+
			"p=[try_to_load_from_cache(r,x) for x in f]; sys.exit(0 if all(isinstance(x,str) and Path(x).is_file() for x in p) else 1)",
		repoID,
	)
	args := append(append([]string{}, py.Prefix...), "-c", code)
	_, err := runCapture(py.Exe, args...)
	return err == nil
}

func ensureSTT(cfg RuntimeConfig, py PythonCommand, st *Status) {
	if sttCached(py, cfg.STT.RepoID) {
		st.STTModel = true
		return
	}
	prompt := fmt.Sprintf("The offline speech-to-text model %s is not cached (about %d MB).\n\nDownload it now from the official Hugging Face model repository?\n\nThis is required for PTT voice transcription.", cfg.STT.ModelName, cfg.STT.ApproxDownloadMB)
	if !askYesNo(prompt) {
		st.MissingFeature = append(st.MissingFeature, "STT model "+cfg.STT.ModelName)
		return
	}
	code := fmt.Sprintf("from huggingface_hub import snapshot_download; snapshot_download(repo_id=%q); print('STT model downloaded')", cfg.STT.RepoID)
	args := append(append([]string{}, py.Prefix...), "-c", code)
	if err := runInteractive(py.Exe, args...); err != nil {
		st.MissingFeature = append(st.MissingFeature, "STT model "+cfg.STT.ModelName+" (download failed)")
		return
	}
	st.STTModel = sttCached(py, cfg.STT.RepoID)
	if !st.STTModel {
		st.MissingFeature = append(st.MissingFeature, "STT model "+cfg.STT.ModelName+" (cache validation failed)")
	}
}

func findOllama() string {
	if p, err := exec.LookPath("ollama.exe"); err == nil {
		return p
	}
	local := os.Getenv("LOCALAPPDATA")
	candidates := []string{
		filepath.Join(local, "Programs", "Ollama", "ollama.exe"),
		filepath.Join(local, "Ollama", "ollama.exe"),
	}
	for _, p := range candidates {
		if p != "" {
			if _, err := os.Stat(p); err == nil {
				return p
			}
		}
	}
	return ""
}

func ollamaList(ollama string) (string, error) {
	out, err := runCapture(ollama, "list")
	if err == nil {
		return out, nil
	}
	// Installed but not running: try to start the local server once.
	cmd := exec.Command(ollama, "serve")
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	if startErr := cmd.Start(); startErr != nil {
		return out, err
	}
	time.Sleep(2 * time.Second)
	return runCapture(ollama, "list")
}

func listHasModel(listing, model string) bool {
	wanted := strings.ToLower(strings.TrimSpace(model))
	for _, line := range strings.Split(listing, "\n") {
		fields := strings.Fields(strings.TrimSpace(line))
		if len(fields) > 0 && strings.ToLower(fields[0]) == wanted {
			return true
		}
	}
	return false
}

func ensureLLM(cfg RuntimeConfig, st *Status) {
	ollama := findOllama()
	if ollama == "" {
		if askYesNo("Ollama is not installed.\n\nRace Engineer uses Ollama for the free local LLM explanation path. The app core can still run without it.\n\nOpen the official Ollama Windows download page now?") {
			_ = openURL(cfg.LLM.DownloadURL)
		}
		st.MissingFeature = append(st.MissingFeature, "Ollama / local LLM")
		return
	}
	st.Ollama = true
	listing, err := ollamaList(ollama)
	if err != nil {
		st.MissingFeature = append(st.MissingFeature, "Ollama service")
		return
	}
	if listHasModel(listing, cfg.LLM.Model) {
		st.LLMModel = true
		return
	}
	prompt := fmt.Sprintf("Ollama is installed, but the Race Engineer model %s is missing.\n\nDownload it now with 'ollama pull %s'?\n\nThe model is not bundled in RaceEngineer.exe.", cfg.LLM.Model, cfg.LLM.Model)
	if !askYesNo(prompt) {
		st.MissingFeature = append(st.MissingFeature, "LLM model "+cfg.LLM.Model)
		return
	}
	if err := runInteractive(ollama, "pull", cfg.LLM.Model); err != nil {
		st.MissingFeature = append(st.MissingFeature, "LLM model "+cfg.LLM.Model+" (download failed)")
		return
	}
	listing, err = ollamaList(ollama)
	st.LLMModel = err == nil && listHasModel(listing, cfg.LLM.Model)
	if !st.LLMModel {
		st.MissingFeature = append(st.MissingFeature, "LLM model "+cfg.LLM.Model+" (validation failed)")
	}
}

func writeStatus(st Status) {
	_ = os.MkdirAll(filepath.Join("analysis", "diagnostics"), 0o755)
	raw, _ := json.MarshalIndent(st, "", "  ")
	_ = os.WriteFile(filepath.Join("analysis", "diagnostics", "bootstrapper_status.json"), append(raw, '\n'), 0o644)
}

func hasArg(name string) bool {
	for _, a := range os.Args[1:] {
		if strings.EqualFold(a, name) {
			return true
		}
	}
	return false
}

func forwardedArgs() []string {
	out := make([]string, 0, len(os.Args)-1)
	for _, a := range os.Args[1:] {
		switch strings.ToLower(a) {
		case "--check-only", "--console":
			continue
		default:
			out = append(out, a)
		}
	}
	return out
}

func launchApp(py PythonCommand, console bool, args []string) error {
	exe := py.Exe
	if !console && len(py.Prefix) == 0 {
		candidate := filepath.Join(filepath.Dir(py.Exe), "pythonw.exe")
		if _, err := os.Stat(candidate); err == nil {
			exe = candidate
		}
	}
	launchArgs := append(append([]string{}, py.Prefix...), "-m", "src.product_launcher")
	launchArgs = append(launchArgs, args...)
	cmd := exec.Command(exe, launchArgs...)
	cmd.Dir, _ = os.Getwd()
	if !console {
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	}
	logf("Launching app: %s %s", exe, strings.Join(launchArgs, " "))
	return cmd.Start()
}

func main() {
	code := mainCode()
	if logFile != nil {
		_ = logFile.Close()
	}
	os.Exit(code)
}

func mainCode() int {
	if runtime.GOOS != "windows" {
		return fail("RaceEngineer.exe is a Windows launcher.")
	}
	exe, err := os.Executable()
	if err != nil {
		return fail("Cannot determine the Race Engineer application folder: " + err.Error())
	}
	root := filepath.Dir(exe)
	if err := os.Chdir(root); err != nil {
		return fail("Cannot open the Race Engineer application folder: " + err.Error())
	}
	_ = os.MkdirAll(filepath.Join("logs", "bootstrapper"), 0o755)
	logFile, _ = os.OpenFile(filepath.Join("logs", "bootstrapper", "stable_v2_launcher.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	logf("=== Stable V2 RC3 cleanup bootstrapper start ===")

	cfg, err := loadConfig("runtime_dependencies.json")
	if err != nil {
		return fail("runtime_dependencies.json is missing or invalid: " + err.Error())
	}
	st := Status{CheckedAtUTC: time.Now().UTC().Format(time.RFC3339), Release: cfg.Release, Windows: true}

	if _, err := os.Stat(filepath.Join("src", "product_launcher.py")); err != nil {
		return fail("The Race Engineer application files are incomplete. src\\product_launcher.py is missing.")
	}

	py, err := ensureVenv(cfg, &st)
	if err != nil {
		writeStatus(st)
		return fail(err.Error())
	}
	if err := ensurePythonPackages(cfg, py, &st); err != nil {
		writeStatus(st)
		return fail(err.Error())
	}

	safeMode := hasArg("--safe-mode")
	if !safeMode {
		ensurePiperVoice(cfg, py, &st)
		ensureSTT(cfg, py, &st)
		ensureLLM(cfg, &st)
	} else {
		st.Notes = append(st.Notes, "Safe mode: optional voice/STT/LLM downloads were not requested.")
	}
	_, ffErr := exec.LookPath("ffmpeg.exe")
	st.FFmpeg = ffErr == nil
	if !st.FFmpeg {
		st.Notes = append(st.Notes, "External ffmpeg not found; current faster-whisper/PyAV path does not require it.")
	}
	st.CoreReady = st.Python && st.VirtualEnv && st.PythonPackages
	writeStatus(st)

	if !st.CoreReady {
		return fail("Race Engineer core dependencies are not ready. See logs\\bootstrapper\\stable_v2_launcher.log.")
	}

	if len(st.MissingFeature) > 0 {
		text := "Core Race Engineer is ready, but these optional/feature dependencies are still missing:\n\n- " + strings.Join(st.MissingFeature, "\n- ") + "\n\nThe deterministic telemetry, overlays and non-AI core can still run. Continue?"
		if message(text, "Race Engineer — Stable V2", mbOKCancel|mbIconWarning) != idOK {
			return 0
		}
	}

	if hasArg("--check-only") {
		text := "Dependency check complete.\n\nCore: READY"
		if len(st.MissingFeature) == 0 {
			text += "\nPiper TTS: READY\nSTT: READY\nOllama + " + cfg.LLM.Model + ": READY"
		} else {
			text += "\nMissing feature dependencies: " + strings.Join(st.MissingFeature, ", ")
		}
		message(text, "Race Engineer — Stable V2", mbOK|mbIconInformation)
		return 0
	}

	if err := launchApp(py, hasArg("--console"), forwardedArgs()); err != nil {
		return fail("Dependencies are ready, but Race Engineer could not be started: " + err.Error())
	}
	return 0
}
