document.addEventListener('DOMContentLoaded', () => {
	// 🔧 CONFIGURATION
	const CONFIG = {
		total: 5, // Total dots on screen (50+ recommended)
		real: 3, // How many actually unlock the video
		reset: 2, // How many are traps (reload page)
		// Decoys automatically fill the rest to reach total
		// If you want exactly 2x fakes per real, set:
		// decoy = CONFIG.real * 2, and adjust total accordingly.
	};

	// Safety check
	if (CONFIG.total < CONFIG.real + CONFIG.reset) {
		CONFIG.total = CONFIG.real + CONFIG.reset + 10;
	}

	const decoy = CONFIG.total - CONFIG.real - CONFIG.reset;
	const types = [
		...Array(CONFIG.real).fill('real'),
		...Array(CONFIG.reset).fill('reset'),
		...Array(decoy).fill('decoy'),
	].sort(() => Math.random() - 0.5);

	const containers = document.querySelectorAll(
		'header, main, footer, .intro, .section, .resource-card',
	);
	const REAL_KEY = '7f3a9b2e'; // Inspectable hint
	let revealed = false;

	const revealVideo = () => {
		if (revealed) return;
		revealed = true;
		const vs = document.getElementById('videoSection');
		const vid = vs?.querySelector('video');
		vs.classList.add('visible');
		vs.scrollIntoView({ behavior: 'smooth', block: 'center' });
		if (vid) vid.play().catch(() => {});

		document.querySelectorAll('.decor-dot').forEach((d) => {
			d.style.pointerEvents = 'none';
			d.style.opacity = '0.3';
			d.style.cursor = 'default';
		});
		console.log('🎥 Video unlocked — bien hecho 👏');
	};

	// Generate dots dynamically
	types.forEach((type) => {
		const dot = document.createElement('button');
		dot.className = 'decor-dot';
		dot.dataset.key = type === 'real' ? REAL_KEY : type;
		dot.setAttribute('aria-hidden', 'true');

		// Safe random placement (10%-90% bounds to prevent overflow)
		const container = containers[Math.floor(Math.random() * containers.length)];
		dot.style.top = `${Math.floor(Math.random() * 80) + 10}%`;
		dot.style.left = `${Math.floor(Math.random() * 80) + 10}%`;

		container.appendChild(dot);

		// Click logic
		dot.addEventListener('click', (e) => {
			e.stopPropagation();
			if (type === 'real') {
				revealVideo();
				dot.style.animation = 'dotPulse 0.6s ease';
				dot.style.boxShadow = '0 0 0 4px #10b981, 0 0 20px rgba(16, 185, 129, 0.6)';
			} else if (type === 'reset') {
				dot.style.background = '#ef4444';
				dot.style.transform = 'scale(1.4) rotate(180deg)';
				console.log('🔄 ¡Trampa activada! Reiniciando...');
				setTimeout(() => location.reload(), 400);
			} else {
				dot.style.transform = 'scale(0.8)';
				console.log('🔍 Nada... sigue buscando.');
				setTimeout(() => {
					dot.style.transform = '';
				}, 200);
			}
		});
	});

	// Keyboard fallback (undocumented)
	document.addEventListener('keydown', (e) => {
		if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'v') {
			e.preventDefault();
			revealVideo();
		}
	});
});
