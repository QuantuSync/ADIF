"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ENLACES = [
  { href: "/", etiqueta: "Expedientes" },
  { href: "/catalogo", etiqueta: "Catálogo" },
  { href: "/conciliacion", etiqueta: "Conciliación" },
  { href: "/revision", etiqueta: "Cola de revisión" },
  { href: "/revision/candidatos-matricula", etiqueta: "Candidatos de matrícula" },
  { href: "/mantenimiento", etiqueta: "Mantenimiento" },
];

export default function NavLinks() {
  const pathname = usePathname();
  // El enlace activo es el de ruta más específica que encaje -- sin esto,
  // "/revision" y "/revision/candidatos-matricula" se marcaban los dos a la
  // vez en la sub-página (el primero es prefijo literal del segundo).
  const masEspecifico = ENLACES.filter(
    (e) => e.href === "/" ? pathname === "/" : pathname?.startsWith(e.href)
  ).sort((a, b) => b.href.length - a.href.length)[0];
  return (
    <>
      {ENLACES.map((enlace) => {
        const activo = enlace.href === masEspecifico?.href;
        return (
          <Link key={enlace.href} href={enlace.href} className={`nav-link${activo ? " active" : ""}`}>
            {enlace.etiqueta}
          </Link>
        );
      })}
    </>
  );
}
