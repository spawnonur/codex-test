/* global Chart */
(function () {
  const jobListEl = document.getElementById('job-list');
  const statusEl = document.getElementById('status');
  const productGrid = document.getElementById('product-grid');
  const productEmpty = document.getElementById('products-empty');
  const imagesGrid = document.getElementById('image-grid');
  const imagesEmpty = document.getElementById('images-empty');
  const chartEmpty = document.getElementById('chart-empty');
  const resultTitle = document.getElementById('result-title');
  const resultMeta = document.getElementById('result-meta');
  const refreshButton = document.getElementById('refresh-button');
  const scrapeForm = document.getElementById('scrape-form');
  const sampleButton = document.getElementById('sample-button');

  const chartCanvas = document.getElementById('chart-canvas');
  const initialJobs = window.__INITIAL_JOBS__ || [];
  const chartPalette = [
    '#2563EB',
    '#10B981',
    '#F97316',
    '#6366F1',
    '#14B8A6',
    '#F43F5E'
  ];

  let chartInstance = null;
  let jobsState = Array.from(initialJobs);

  function setStatus(message, type) {
    if (!statusEl) return;
    statusEl.textContent = message || '';
    statusEl.className = `status${type ? ` ${type}` : ''}`;
  }

  function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('tr-TR', {
      dateStyle: 'medium',
      timeStyle: 'short'
    });
  }

  function renderJobList() {
    if (!jobListEl) return;
    jobListEl.innerHTML = '';
    if (!jobsState.length) {
      const emptyItem = document.createElement('li');
      emptyItem.textContent = 'Henüz tarama yok.';
      emptyItem.classList.add('empty');
      jobListEl.appendChild(emptyItem);
      return;
    }

    jobsState.forEach((job, index) => {
      const item = document.createElement('li');
      item.dataset.id = job.id;
      const title = job.title || job.chart_title || job.url;
      item.innerHTML = `<strong>${title}</strong>`;
      const meta = document.createElement('span');
      meta.textContent = [
        job.chart_title,
        `${job.product_count || 0} ürün`,
        formatDate(job.created_at)
      ]
        .filter(Boolean)
        .join(' • ');
      item.appendChild(meta);
      item.addEventListener('click', () => loadJob(job.id));
      if (index === 0) {
        item.classList.add('active');
      }
      jobListEl.appendChild(item);
    });
  }

  function highlightJob(jobId) {
    if (!jobListEl) return;
    [...jobListEl.children].forEach((node) => {
      if (node.dataset && node.dataset.id === String(jobId)) {
        node.classList.add('active');
      } else {
        node.classList.remove('active');
      }
    });
  }

  function destroyChart() {
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }
  }

  function renderChart(job) {
    const datasets = job.datasets || [];
    if (!datasets.length) {
      destroyChart();
      chartEmpty.classList.remove('hidden');
      return;
    }

    chartEmpty.classList.add('hidden');
    const labels = datasets[0].labels || [];
    const chartData = {
      labels,
      datasets: datasets.map((dataset, index) => {
        const color = dataset.color || chartPalette[index % chartPalette.length];
        return {
          label: dataset.label,
          data: dataset.values,
          borderColor: color,
          backgroundColor: color + '33',
          fill: true,
          tension: 0.35
        };
      })
    };

    destroyChart();
    chartInstance = new Chart(chartCanvas, {
      type: 'line',
      data: chartData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0
            }
          }
        },
        plugins: {
          legend: {
            position: 'bottom'
          }
        }
      }
    });
  }

  function renderProducts(job) {
    const products = job.products || [];
    productGrid.innerHTML = '';
    if (!products.length) {
      productEmpty.classList.remove('hidden');
      return;
    }
    productEmpty.classList.add('hidden');

    products.forEach((product) => {
      const card = document.createElement('article');
      card.className = 'product-card';
      if (product.image_url) {
        const img = document.createElement('img');
        img.src = product.image_url;
        img.alt = product.name || 'Ürün görseli';
        card.appendChild(img);
      }
      const title = document.createElement('h4');
      title.textContent = product.name || 'Adsız ürün';
      card.appendChild(title);
      if (product.description) {
        const desc = document.createElement('p');
        desc.textContent = product.description;
        card.appendChild(desc);
      }
      if (product.price) {
        const price = document.createElement('span');
        price.className = 'price';
        const currency = product.currency || '';
        price.textContent = `${product.price.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ${currency}`.trim();
        card.appendChild(price);
      }
      productGrid.appendChild(card);
    });
  }

  function renderImages(job) {
    const images = job.images || [];
    imagesGrid.innerHTML = '';
    if (!images.length) {
      imagesEmpty.classList.remove('hidden');
      return;
    }
    imagesEmpty.classList.add('hidden');

    images.forEach((image) => {
      const figure = document.createElement('figure');
      const img = document.createElement('img');
      img.src = image.url;
      img.alt = image.alt || 'Sayfadan alınan görsel';
      figure.appendChild(img);
      const caption = document.createElement('figcaption');
      const contextText = image.context === 'product' ? 'Ürün görseli' : 'Genel görsel';
      caption.textContent = image.alt ? `${image.alt} • ${contextText}` : contextText;
      figure.appendChild(caption);
      imagesGrid.appendChild(figure);
    });
  }

  function updateResultHeader(job) {
    const metaParts = [];
    if (job.chart_title) metaParts.push(job.chart_title);
    if (job.datasets?.length) metaParts.push(`${job.datasets.length} veri seti`);
    if (job.products?.length) metaParts.push(`${job.products.length} ürün`);
    if (job.created_at) metaParts.push(formatDate(job.created_at));
    resultTitle.textContent = job.title || job.url || 'Sonuç';
    resultMeta.textContent = metaParts.join(' • ');
  }

  async function loadJob(jobId) {
    if (!jobId) return;
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      if (!response.ok) {
        throw new Error('Kayıt getirilemedi');
      }
      const payload = await response.json();
      highlightJob(jobId);
      renderChart(payload);
      renderProducts(payload);
      renderImages(payload);
      updateResultHeader(payload);
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  async function refreshJobs() {
    try {
      const response = await fetch('/api/jobs');
      if (!response.ok) {
        throw new Error('Liste alınamadı');
      }
      jobsState = await response.json();
      renderJobList();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  async function submitScrape(formData) {
    setStatus('Tarama başlatıldı…', '');
    try {
      const response = await fetch('/scrape', {
        method: 'POST',
        body: formData
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || 'Tarama sırasında hata oluştu');
      }
      const job = payload.job;
      jobsState = [
        {
          id: job.id,
          url: job.url,
          title: job.title,
          chart_title: job.chart_title,
          created_at: job.created_at,
          product_count: job.products?.length || 0,
          dataset_count: job.datasets?.length || 0
        },
        ...jobsState
      ];
      renderJobList();
      highlightJob(job.id);
      renderChart(job);
      renderProducts(job);
      renderImages(job);
      updateResultHeader(job);
      setStatus('Tarama tamamlandı.', 'success');
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  if (scrapeForm) {
    scrapeForm.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!scrapeForm.reportValidity()) {
        return;
      }
      const formData = new FormData(scrapeForm);
      submitScrape(formData);
    });
  }

  if (sampleButton) {
    sampleButton.addEventListener('click', () => {
      const formData = new FormData();
      formData.append('use_sample', '1');
      submitScrape(formData);
    });
  }

  if (refreshButton) {
    refreshButton.addEventListener('click', () => {
      refreshJobs();
    });
  }

  renderJobList();
  if (jobsState.length) {
    loadJob(jobsState[0].id);
  }
})();
