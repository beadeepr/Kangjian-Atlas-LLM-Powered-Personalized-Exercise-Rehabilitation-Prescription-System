const apiBase = window.API_BASE || "http://localhost:8000/api";

async function loadPrescriptions() {
  try {
    const resp = await fetch(`${apiBase}/prescriptions`);
    const data = await resp.json();
    const list = document.getElementById('prescriptionList');
    if (!Array.isArray(data) || data.length === 0) {
      list.textContent = '暂无处方记录。';
      return;
    }
    list.innerHTML = data.map(renderPrescription).join('');
  } catch (error) {
    document.getElementById('prescriptionList').textContent = '加载失败，请检查后端服务。';
  }
}

function renderPrescription(prescription) {
  const header = [
    prescription.patient_name ? `患者：${prescription.patient_name}` : '',
    prescription.patient_age ? `年龄：${prescription.patient_age}` : ''
  ].filter(Boolean).join(' | ');

  return `
    <div class="card">
      <h3>处方 #${prescription.id || 'N/A'}</h3>
      ${header ? `<div class="meta">${header}</div>` : ''}
      <p>${prescription.summary.replace(/\n/g, '<br>')}</p>
      <ul>
        ${prescription.actions.map(action => `
          <li>
            <strong>${action.name}</strong>：${action.sets}组 x ${action.reps}次
            ${action.note ? `（${action.note}）` : ''}
          </li>
        `).join('')}
      </ul>
    </div>
  `;
}

document.getElementById('submit').addEventListener('click', async () => {
  const name = document.getElementById('name').value;
  const age = parseInt(document.getElementById('age').value, 10) || undefined;
  const symptoms = document.getElementById('symptoms').value;
  const history = document.getElementById('history').value;
  const resp = await fetch(`${apiBase}/generate_prescription`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, age, symptoms, history })
  });
  const data = await resp.json();
  document.getElementById('result').textContent = JSON.stringify(data, null, 2);
  await loadPrescriptions();
});

let stream;
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');

document.getElementById('startCam').addEventListener('click', async () => {
  stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  video.srcObject = stream;
});

document.getElementById('sendFrame').addEventListener('click', async () => {
  if (!video.srcObject) {
    document.getElementById('feedback').textContent = '请先启动摄像头。';
    return;
  }
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const resp = await fetch(`${apiBase}/correct_pose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keypoints: [] })
  });
  const data = await resp.json();
  document.getElementById('feedback').textContent = data.feedback.join('\n');
});

window.addEventListener('load', loadPrescriptions);
