import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const STATUS_COLOR = { healthy: 0x22c55e, warning: 0xf59e0b, critical: 0xef4444 };

export default function DigitalTwin({ sources, selectedId }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const nodesRef = useRef([]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    const camera = new THREE.PerspectiveCamera(55, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.set(0, 4, 7);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(3, 5, 4);
    scene.add(dirLight);

    const grid = new THREE.GridHelper(10, 10, 0x334155, 0x1e293b);
    scene.add(grid);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    sceneRef.current = scene;

    const clock = new THREE.Clock();
    let raf;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();
      nodesRef.current.forEach((n, i) => {
        if (n) {
          n.position.y = 0.55 + Math.sin(t * 1.2 + i) * 0.12;
          n.rotation.y = t * 0.6 + i;
        }
      });
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      cancelAnimationFrame(raf);
      controls.dispose();
      nodesRef.current.forEach((n) => {
        if (n) {
          scene.remove(n);
          n.geometry.dispose();
          n.material.dispose();
        }
      });
      nodesRef.current = [];
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    nodesRef.current.forEach((n) => {
      if (n) {
        scene.remove(n);
        n.geometry.dispose();
        n.material.dispose();
      }
    });
    nodesRef.current = [];

    const cols = Math.max(1, Math.ceil(Math.sqrt(Math.max(sources.length, 1))));
    sources.forEach((s, i) => {
      const color = STATUS_COLOR[s.status] || STATUS_COLOR.healthy;
      const selected = s.id === selectedId;
      const geo = new THREE.SphereGeometry(selected ? 0.5 : 0.38, 24, 24);
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: selected ? 0.5 : 0.22,
      });
      const mesh = new THREE.Mesh(geo, mat);
      const x = (i % cols) - (cols - 1) / 2;
      const z = Math.floor(i / cols) - Math.floor(sources.length / cols) / 2;
      mesh.position.set(x * 1.8, 0.55, z * 1.8);
      scene.add(mesh);
      nodesRef.current.push(mesh);
    });
  }, [sources, selectedId]);

  return <div ref={mountRef} style={{ width: '100%', height: '100%', minHeight: 180 }} />;
}
