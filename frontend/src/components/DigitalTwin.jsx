import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const STATUS_COLOR = { healthy: 0x22c55e, warning: 0xf59e0b, critical: 0xef4444 };
const STATUS_EMISSIVE = { healthy: 0x22c55e, warning: 0xf59e0b, critical: 0xef4444 };

export default function DigitalTwin({ sources, selectedId }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const nodesRef = useRef([]);
  const glowRef = useRef([]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e1a);
    scene.fog = new THREE.Fog(0x0a0e1a, 12, 25);

    const camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.set(0, 5, 8);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
    dirLight.position.set(5, 8, 5);
    scene.add(dirLight);
    const pointLight = new THREE.PointLight(0x22d3ee, 0.6, 20);
    pointLight.position.set(0, 3, 0);
    scene.add(pointLight);

    const grid = new THREE.GridHelper(14, 14, 0x2a3a5c, 0x1a2440);
    scene.add(grid);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 4;
    controls.maxDistance = 15;
    sceneRef.current = scene;

    const clock = new THREE.Clock();
    let raf;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();
      nodesRef.current.forEach((n, i) => {
        if (n) {
          n.position.y = 0.6 + Math.sin(t * 1.5 + i * 0.8) * 0.15;
          n.rotation.y = t * 0.4 + i;
        }
      });
      glowRef.current.forEach((g, i) => {
        if (g) {
          g.position.y = 0.6 + Math.sin(t * 1.5 + i * 0.8) * 0.15;
          const scale = 1.0 + Math.sin(t * 2 + i) * 0.15;
          g.scale.set(scale, scale, scale);
          g.material.opacity = 0.12 + Math.sin(t * 2 + i) * 0.06;
        }
      });
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      cancelAnimationFrame(raf);
      controls.dispose();
      [...nodesRef.current, ...glowRef.current].forEach((n) => {
        if (n) { scene.remove(n); n.geometry?.dispose(); n.material?.dispose(); }
      });
      nodesRef.current = [];
      glowRef.current = [];
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    [...nodesRef.current, ...glowRef.current].forEach((n) => {
      if (n) { scene.remove(n); n.geometry?.dispose(); n.material?.dispose(); }
    });
    nodesRef.current = [];
    glowRef.current = [];

    const cols = Math.max(1, Math.ceil(Math.sqrt(Math.max(sources.length, 1))));
    sources.forEach((s, i) => {
      const color = STATUS_COLOR[s.status] || STATUS_COLOR.healthy;
      const selected = s.id === selectedId;

      const geo = new THREE.SphereGeometry(selected ? 0.5 : 0.38, 32, 32);
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: selected ? 0.6 : 0.25,
        metalness: 0.3,
        roughness: 0.4,
      });
      const mesh = new THREE.Mesh(geo, mat);
      const x = (i % cols) - (cols - 1) / 2;
      const z = Math.floor(i / cols) - Math.floor(sources.length / cols) / 2;
      mesh.position.set(x * 2.0, 0.6, z * 2.0);
      scene.add(mesh);
      nodesRef.current.push(mesh);

      const glowGeo = new THREE.SphereGeometry(selected ? 0.7 : 0.52, 24, 24);
      const glowMat = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.12,
        side: THREE.BackSide,
      });
      const glowMesh = new THREE.Mesh(glowGeo, glowMat);
      glowMesh.position.copy(mesh.position);
      scene.add(glowMesh);
      glowRef.current.push(glowMesh);
    });
  }, [sources, selectedId]);

  return <div ref={mountRef} style={{ width: '100%', height: '100%', minHeight: 180 }} />;
}
