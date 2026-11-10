"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import type { GeoPoint } from "@/lib/api";

type Props = {
  polyline: GeoPoint[];
  position: { lat: number; lng: number; heading: number };
  origin: GeoPoint;
  destination: GeoPoint;
};

export function TrackingMap({ polyline, position, origin, destination }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{
    map: import("leaflet").Map;
    marker: import("leaflet").Marker;
    L: typeof import("leaflet");
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const leafletMod = await import("leaflet");
      const L = (leafletMod.default ?? leafletMod) as typeof import("leaflet");
      if (!containerRef.current || cancelled) return;
      const map = L.map(containerRef.current, { scrollWheelZoom: true, zoomControl: true });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 18,
      }).addTo(map);
      const route = L.polyline(
        polyline.map((point) => [point.lat, point.lng]),
        { color: "#0f766e", weight: 5, opacity: 0.85 },
      ).addTo(map);
      L.circleMarker([origin.lat, origin.lng], { radius: 7, color: "#0b1f3a", fillColor: "#0b1f3a", fillOpacity: 1 }).addTo(map).bindTooltip(origin.name || "Origin");
      L.circleMarker([destination.lat, destination.lng], { radius: 7, color: "#0f766e", fillColor: "#0f766e", fillOpacity: 1 }).addTo(map).bindTooltip(destination.name || "Destination");
      const icon = L.divIcon({
        className: "bgm-bus-marker",
        html: `<div class="bgm-bus-rotator" style="transform:rotate(${position.heading}deg)"><span></span></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
      const marker = L.marker([position.lat, position.lng], { icon }).addTo(map);
      map.fitBounds(route.getBounds().pad(0.18));
      mapRef.current = { map, marker, L };
    })();
    return () => {
      cancelled = true;
      mapRef.current?.map.remove();
      mapRef.current = null;
    };
    // polyline identity is stable enough for a trip; remount on trip change via key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const current = mapRef.current;
    if (!current) return;
    current.marker.setLatLng([position.lat, position.lng]);
    current.marker.setIcon(
      current.L.divIcon({
        className: "bgm-bus-marker",
        html: `<div class="bgm-bus-rotator" style="transform:rotate(${position.heading}deg)"><span></span></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      }),
    );
  }, [position.lat, position.lng, position.heading]);

  return <div ref={containerRef} className="h-[420px] w-full overflow-hidden rounded-3xl border border-navy/10" />;
}
