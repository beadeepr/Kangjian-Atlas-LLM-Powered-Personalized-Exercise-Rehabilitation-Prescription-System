const apiBase = window.API_BASE || "http://localhost:8000/api";

document.getElementById('submit').addEventListener('click', async () => {
  const symptoms = document.getElementById('symptoms').value;
  const resp = await fetch(`${apiBase}/generate_prescription`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symptoms })
  });
  const data = await resp.json();
  document.getElementById('result').textContent = JSON.stringify(data, null, 2);
});

let stream;
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');

document.getElementById('startCam').addEventListener('click', async () => {
  stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  video.srcObject = stream;
});

document.getElementById('sendFrame').addEventListener('click', async () => {
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg'));
  const form = new FormData();
  form.append('frame', blob, 'frame.jpg');
  const resp = await fetch(`${apiBase}/correct_pose`, { method: 'POST', body: JSON.stringify({ keypoints: null }), headers: { 'Content-Type': 'application/json' } });
  const data = await resp.json();
  document.getElementById('feedback').textContent = data.feedback.join('\n');
});
