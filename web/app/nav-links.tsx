"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ENLACES = [
  { href: "/", etiqueta: "Expedientes" },
  { href: "/catalogo", etiqueta: "Catálogo" },
  { href: "/revision", etiqueta: "Cola de revisión" },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <>
      {ENLACES.map((enlace) => {
        const activo = enlace.href === "/" ? pathname === "/" : pathname?.startsWith(enlace.href);
        return (
          <Link key={enlace.href} href={enlace.href} className={`nav-link${activo ? " active" : ""}`}>
            {enlace.etiqueta}
          </Link>
        );
      })}
    </>
  );
}
