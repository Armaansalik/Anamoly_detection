import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const STATUS_COLOR = { healthy: 0x22c55e, warning: 0xf59e0b, critical: 0xef4444 };
const STATUS_LABEL = { healthy: 'Running OK', warning: 'Needs Attention', critical: 'ALERT — Check Now' };

export default function DigitalTwin({ sources, selectedId, onSelectSource }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const nodesRef = useRef([]);
  const glowRef = useRef([]);
  const labelsRef = useRef([]);
  const [hovered, setHovered] = useState(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050a15);
    scene.fog = new THREE.Fog(0x050a15, 14, 30);

    const camera = new THREE.PerspectiveCamera(45, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.set(0, 6, 10);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 10, 5);
    dirLight.castShadow = true;
    scene.add(dirLight);
    const pointLight = new THREE.PointLight(0x22d3ee, 0.5, 25);
    pointLight.position.set(0, 4, 0);
    scene.add(pointLight);

    const grid = new THREE.GridHelper(16, 16, 0x1e3050, 0x111d35);
    grid.position.y = -0.01;
    scene.add(grid);

    const conveyorGeo = new THREE.BoxGeometry(12, 0.05, 0.8);
    const conveyorMat = new THREE.MeshStandardMaterial({ color: 0x1e3050, metalness: 0.6, roughness: 0.4 });
    const conveyor = new THREE.Mesh(conveyorGeo, conveyorMat);
    conveyor.position.set(0, 0.03, 0);
    conveyor.receiveShadow = true;
    scene.add(conveyor);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 4;
    controls.maxDistance = 18;
    controls.maxPolarAngle = Math.PI / 2.1;
    sceneRef.current = scene;

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onPointerMove = (e) => {
      const rect = mount.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(nodesRef.current);
      if (hits.length > 0) {
        const idx = nodesRef.current.indexOf(hits[0].object);
        if (idx >= 0 && sources[idx]) {
          mount.style.cursor = 'pointer';
          setHovered(sources[idx]);
          return;
        }
      }
      mount.style.cursor = 'default';
      setHovered(null);
    };

    const onClick = (e) => {
      const rect = mount.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(nodesRef.current);
      if (hits.length > 0) {
        const idx = nodesRef.current.indexOf(hits[0].object);
        if (idx >= 0 && sources[idx] && onSelectSource) {
          onSelectSource(sources[idx].id);
        }
      }
    };

    mount.addEventListener('pointermove', onPointerMove);
    mount.addEventListener('click', onClick);

    const clock = new THREE.Clock();
    let raf;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();
      nodesRef.current.forEach((n, i) => {
        if (n) {
          n.position.y = 0.6 + Math.sin(t * 1.5 + i * 0.8) * 0.12;
          n.rotation.y = t * 0.3 + i;
        }
      });
      glowRef.current.forEach((g, i) => {
        if (g) {
          g.position.y = 0.6 + Math.sin(t * 1.5 + i * 0.8) * 0.12;
          const pulse = 1.0 + Math.sin(t * 2.5 + i) * 0.12;
          g.scale.set(pulse, pulse, pulse);
          g.material.opacity = 0.08 + Math.sin(t * 2 + i) * 0.04;
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
      mount.removeEventListener('pointermove', onPointerMove);
      mount.removeEventListener('click', onClick);
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

    const spacing = 2.2;
    const cols = Math.max(1, Math.ceil(Math.sqrt(Math.max(sources.length, 1))));
    sources.forEach((s, i) => {
      const color = STATUS_COLOR[s.status] || STATUS_COLOR.healthy;
      const selected = s.id === selectedId;

      const baseGeo = new THREE.CylinderGeometry(0.15, 0.25, 0.5, 16);
      const baseMat = new THREE.MeshStandardMaterial({ color: 0x1e3050, metalness: 0.7, roughness: 0.3 });
      const baseMesh = new THREE.Mesh(baseGeo, baseMat);

      const bodyGeo = new THREE.CylinderGeometry(0.35, 0.4, 0.8, 24);
      const bodyMat = new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: selected ? 0.5 : 0.2,
        metalness: 0.4,
        roughness: 0.3,
      });
      const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);

      const topGeo = new THREE.SphereGeometry(0.3, 24, 24);
      const topMat = new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: selected ? 0.7 : 0.3,
        metalness: 0.3,
        roughness: 0.2,
      });
      const topMesh = new THREE.Mesh(topGeo, topMat);

      const group = new THREE.Group();
      group.add(baseMesh);
      baseMesh.position.y = 0;
      bodyMesh.position.y = 0.5;
      topMesh.position.y = 1.0;
      group.add(bodyMesh);
      group.add(topMesh);

      const x = (i % cols) * spacing - ((cols - 1) * spacing) / 2;
      const z = Math.floor(i / cols) * spacing - Math.floor(sources.length / cols) * spacing / 2;
      group.position.set(x, 0.05, z);
      group.userData = { sourceId: s.id, index: i };
      scene.add(group);
      nodesRef.current.push(group);

      const glowGeo = new THREE.SphereGeometry(0.5, 24, 24);
      const glowMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.08,
        side: THREE.BackSide,
      });
      const glowMesh = new THREE.Mesh(glowGeo, glowMat);
      glowMesh.position.copy(topMesh.position);
      group.add(glowMesh);
      glowRef.current.push(glowMesh);

      if (selected) {
        const ringGeo = new THREE.RingGeometry(0.6, 0.7, 32);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.4, side: THREE.DoubleSide });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 0.02;
        group.add(ring);
      }
    });
  }, [sources, selectedId, onSelectSource]);

  const hoveredSource = hovered;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: 200 }}>
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
      {hoveredSource && (
        <div style={{
          position: 'absolute',
          bottom: 12,
          left: 12,
          background: 'rgba(13,21,40,0.95)',
          border: '1px solid ' + (STATUS_COLOR[hoveredSource.status] ? '#' + STATUS_COLOR[hoveredSource.status].toString(16).padStart(6, '0') : '#1e3050'),
          borderRadius: 10,
          padding: '10px 14px',
          fontSize: 12,
          color: '#e8edf5',
          backdropFilter: 'blur(8px)',
          minWidth: 180,
          animation: 'fadeIn 0.2s ease',
          zIndex: 10,
          pointerEvents: 'none',
        }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>{hoveredSource.id}</div>
          <div style={{ color: '#6b7fa0', marginBottom: 2 }}>Domain: {hoveredSource.domain}</div>
          <div style={{
            color: STATUS_COLOR[hoveredSource.status] ? '#e8edf5' : '#6b7fa0',
            fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 6
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: STATUS_COLOR[hoveredSource.status] || '#6b7fa0',
              display: 'inline-block',
            }} />
            {STATUS_LABEL[hoveredSource.status] || 'Unknown'}
          </div>
          <div style={{ color: '#6b7fa0', marginTop: 4 }}>
            Health: {Math.round((hoveredSource.health_score || 0) * 100)}%
          </div>
          {hoveredSource.latest && Object.keys(hoveredSource.latest).length > 0 && (
            <div style={{ marginTop: 6, borderTop: '1px solid #1e3050', paddingTop: 6 }}>
              {Object.entries(hoveredSource.latest).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <span style={{ color: '#6b7fa0' }}>{k}</span>
                  <span style={{ fontWeight: 600 }}>{typeof v === 'number' ? v.toFixed(1) : v}</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ color: '#22d3ee', marginTop: 6, fontSize: 10 }}>Click to select and view details</div>
        </div>
      )}
      <div style={{
        position: 'absolute',
        top: 8,
        left: 12,
        fontSize: 10,
        color: '#6b7fa0',
        display: 'flex',
        gap: 12,
      }}>
        <span>&#x1F5B1; Drag to rotate</span>
        <span>&#x1F50D; Scroll to zoom</span>
        <span>&#x1F446; Click machine to select</span>
      </div>
    </div>
  );
}
