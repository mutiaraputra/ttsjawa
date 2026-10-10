/* Frontend TTS Jawa. Semua inferensi dikerjakan backend Modal;
   berkas ini hanya mengumpulkan masukan lalu memutar hasilnya. */

const BAWAAN = {
  url: "https://mutiarakom--ttsjawa.modal.run",
  bahasa: { id: "Indonesia", jv: "Jawa", su: "Sunda" },
  pembicara: [
    { id: "wibowo", nama: "Wibowo", deskripsi: "Suara jantan berwibawa", bahasa: "id" },
    { id: "ardi", nama: "Ardi", deskripsi: "Suara lembut dan hangat", bahasa: "id" },
    { id: "gadis", nama: "Gadis", deskripsi: "Suara perempuan yang merdu", bahasa: "id" },
    { id: "JV-00264", nama: "Juminten", deskripsi: "Suara perempuan Jawa", bahasa: "jv" },
    { id: "SU-00060", nama: "Asep", deskripsi: "Suara lelaki Sunda", bahasa: "su" },
  ],
  maksTeks: 1000,
  kecepatanDefault: 1.0,
};

const el = (id) => document.getElementById(id);
const dom = {
  teks: el("teks"),
  hitungTeks: el("hitung-teks"),
  maksTeks: el("maks-teks"),
  kecepatan: el("kecepatan"),
  nilaiKecepatan: el("nilai-kecepatan"),
  bahasa: el("bahasa"),
  pembicara: el("pembicara"),
  proses: el("tombol-proses"),
  segarkan: el("tombol-segarkan"),
  status: el("status"),
  audio: el("audio"),
  unduh: el("tautan-unduh"),
  urlBackend: el("url-backend"),
  kodeAkses: el("kode-akses"),
  uji: el("tombol-uji"),
};

const konfigurasi = {
  bahasa: BAWAAN.bahasa,
  pembicara: BAWAAN.pembicara,
  maksTeks: BAWAAN.maksTeks,
};

let urlAudioSebelumnya = null;

function urlBackend() {
  return (localStorage.getItem("ttsjawa.url") || BAWAAN.url).replace(/\/+$/, "");
}

function kodeAkses() {
  return localStorage.getItem("ttsjawa.token") || "";
}

function setStatus(pesan, jenis) {
  dom.status.textContent = pesan;
  dom.status.dataset.jenis = jenis || "";
}

/* Pengaturan disimpan di localStorage agar bisa dipakai ulang, tapi tetap
   bisa ditimpa lewat query string saat pertama kali dibuka. */
function muatPengaturan() {
  const param = new URLSearchParams(location.search);
  if (param.get("api")) localStorage.setItem("ttsjawa.url", param.get("api"));
  if (param.get("token")) localStorage.setItem("ttsjawa.token", param.get("token"));

  dom.urlBackend.value = urlBackend();
  dom.kodeAkses.value = kodeAkses();

  dom.urlBackend.addEventListener("change", () => {
    localStorage.setItem("ttsjawa.url", dom.urlBackend.value.trim());
    muatPembicara();
  });
  dom.kodeAkses.addEventListener("change", () => {
    localStorage.setItem("ttsjawa.token", dom.kodeAkses.value.trim());
  });
}

async function panggil(path, opsi = {}) {
  const adaBody = opsi.body !== undefined;
  const respons = await fetch(urlBackend() + path, {
    ...opsi,
    headers: {
      "X-Access-Token": kodeAkses(),
      ...(adaBody ? { "Content-Type": "application/json" } : {}),
      ...(opsi.headers || {}),
    },
  });

  if (!respons.ok) {
    let pesan = `${respons.status} ${respons.statusText}`;
    try {
      pesan = (await respons.json()).detail || pesan;
    } catch { /* badan bukan JSON, pakai pesan default */ }
    const galat = new Error(pesan);
    galat.status = respons.status;
    throw galat;
  }
  return respons;
}

function isiDropdownBahasa() {
  const pilihan = dom.bahasa.value;
  dom.bahasa.innerHTML = "";
  for (const [kode, nama] of Object.entries(konfigurasi.bahasa)) {
    const opsi = document.createElement("option");
    opsi.value = kode;
    opsi.textContent = nama;
    dom.bahasa.append(opsi);
  }
  if (pilihan && konfigurasi.bahasa[pilihan]) dom.bahasa.value = pilihan;
}

/* Memilih bahasa menyaring daftar pembicara, karena model v1.2 tidak punya
   embedding bahasa: aksen ditentukan oleh pembicaranya. */
function isiDropdownPembicara() {
  const dipilih = dom.pembicara.value;
  const kodeBahasa = dom.bahasa.value;
  dom.pembicara.innerHTML = "";

  const cocok = konfigurasi.pembicara.filter((p) => p.bahasa === kodeBahasa);
  for (const p of cocok) {
    const opsi = document.createElement("option");
    opsi.value = p.id;
    opsi.textContent = `${p.nama} - ${p.deskripsi}`;
    dom.pembicara.append(opsi);
  }
  if (cocok.some((p) => p.id === dipilih)) dom.pembicara.value = dipilih;
}

async function muatPembicara() {
  setStatus("Memuat daftar pembicara dari backend...", "proses");
  try {
    const data = await (await panggil("/speakers")).json();
    konfigurasi.bahasa = data.bahasa;
    konfigurasi.pembicara = data.pembicara;
    konfigurasi.maksTeks = data.maks_teks;
    if (data.kecepatan?.default) {
      dom.kecepatan.value = data.kecepatan.default;
      perbaruiKecepatan();
    }
    dom.maksTeks.textContent = konfigurasi.maksTeks;
    isiDropdownBahasa();
    isiDropdownPembicara();
    perbaruiHitung();
    setStatus("Backend siap.", "sukses");
  } catch (galat) {
    isiDropdownBahasa();
    isiDropdownPembicara();
    setStatus(
      galat.status === 401
        ? "Kode akses ditolak backend. Isi Kode Akses di Pengaturan Backend."
        : `Backend belum bisa dihubungi (${galat.message}). Memakai daftar bawaan.`,
      "gagal",
    );
  }
}

function perbaruiKecepatan() {
  dom.nilaiKecepatan.textContent = Number(dom.kecepatan.value).toFixed(2);
}

function perbaruiHitung() {
  const jumlah = dom.teks.value.length;
  dom.hitungTeks.textContent = jumlah;
  dom.hitungTeks.classList.toggle("lewat", jumlah > konfigurasi.maksTeks);
}

/* Cold start container Modal bisa puluhan detik, jadi pesannya bertahap. */
function mulaiPengingat(waktuMulai) {
  const tahap = [
    [8000, "Backend sedang membangunkan container (cold start)..."],
    [25000, "Masih memuat model 330 MB, mohon tunggu..."],
    [50000, "Menyintesis suara, hampir selesai..."],
  ];
  const id = setInterval(() => {
    const lewat = Date.now() - waktuMulai;
    for (const [batas, pesan] of tahap) {
      if (lewat >= batas) setStatus(`${pesan} (${Math.round(lewat / 1000)} detik)`, "proses");
    }
  }, 1000);
  return () => clearInterval(id);
}

async function lakukanInferensi() {
  const teks = dom.teks.value.trim();
  if (!teks) return setStatus("Teks masih kosong.", "gagal");
  if (teks.length > konfigurasi.maksTeks) {
    return setStatus(`Teks maksimal ${konfigurasi.maksTeks} karakter.`, "gagal");
  }

  dom.proses.disabled = true;
  const waktuMulai = Date.now();
  const hentikanPengingat = mulaiPengingat(waktuMulai);
  setStatus("Mengirim teks ke backend...", "proses");

  try {
    const respons = await panggil("/synthesize", {
      method: "POST",
      body: JSON.stringify({
        teks,
        pembicara: dom.pembicara.value,
        kecepatan: Number(dom.kecepatan.value),
      }),
    });

    const wav = await respons.blob();
    if (urlAudioSebelumnya) URL.revokeObjectURL(urlAudioSebelumnya);
    urlAudioSebelumnya = URL.createObjectURL(wav);

    dom.audio.src = urlAudioSebelumnya;
    dom.unduh.href = urlAudioSebelumnya;
    dom.unduh.hidden = false;
    await dom.audio.play().catch(() => {});

    const detik = ((Date.now() - waktuMulai) / 1000).toFixed(1);
    const ukuran = (wav.size / 1024).toFixed(0);
    setStatus(`Selesai dalam ${detik} detik (${ukuran} KB).`, "sukses");
  } catch (galat) {
    if (galat.status === 401) {
      setStatus("Kode akses ditolak. Perbaiki di Pengaturan Backend.", "gagal");
    } else if (galat instanceof TypeError) {
      setStatus("Gagal menghubungi backend. Periksa URL Backend dan koneksi Anda.", "gagal");
    } else {
      setStatus(`Gagal: ${galat.message}`, "gagal");
    }
  } finally {
    hentikanPengingat();
    dom.proses.disabled = false;
  }
}

async function ujiKoneksi() {
  setStatus("Menguji koneksi ke backend...", "proses");
  const waktuMulai = Date.now();
  try {
    const data = await (await panggil("/healthz")).json();
    const detik = ((Date.now() - waktuMulai) / 1000).toFixed(1);
    setStatus(
      `Backend siap dalam ${detik} detik. Sample rate ${data.sample_rate} Hz, ` +
        `${data.pembicara.length} pembicara.`,
      "sukses",
    );
  } catch (galat) {
    setStatus(`Backend tidak terjangkau: ${galat.message}`, "gagal");
  }
}

function putarContoh(berkas) {
  if (urlAudioSebelumnya) URL.revokeObjectURL(urlAudioSebelumnya);
  urlAudioSebelumnya = null;
  dom.audio.src = berkas;
  dom.unduh.hidden = true;
  setStatus(`Memutar contoh: ${berkas}`, "proses");
  dom.audio.play().catch(() => setStatus("Peramban menolak pemutaran otomatis.", "gagal"));
}

dom.kecepatan.addEventListener("input", perbaruiKecepatan);
dom.teks.addEventListener("input", perbaruiHitung);
dom.bahasa.addEventListener("change", isiDropdownPembicara);
dom.proses.addEventListener("click", lakukanInferensi);
dom.segarkan.addEventListener("click", muatPembicara);
dom.uji.addEventListener("click", ujiKoneksi);
document.querySelectorAll("[data-contoh]").forEach((tombol) => {
  tombol.addEventListener("click", () => putarContoh(tombol.dataset.contoh));
});

muatPengaturan();
perbaruiKecepatan();
isiDropdownBahasa();
isiDropdownPembicara();
perbaruiHitung();
muatPembicara();
