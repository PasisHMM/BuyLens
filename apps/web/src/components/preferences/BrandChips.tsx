"use client";

import { Check, Plus } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { useApp } from "@/app/providers";
import { cx } from "@/components/ui/primitives";
import type { Brand } from "@/lib/api";

const FEATURED = 4;

export function BrandChips({
  selected,
  onChange,
}: {
  selected: Brand[];
  onChange: (brands: Brand[]) => void;
}) {
  const { api } = useApp();
  const [featured, setFeatured] = useState<Brand[]>([]);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Brand[]>([]);
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void api.searchBrands(undefined, FEATURED).then(setFeatured);
  }, [api]);

  useEffect(() => {
    if (!adding) return;
    const t = setTimeout(
      () => void api.searchBrands(query, 8).then(setResults),
      150,
    );
    return () => clearTimeout(t);
  }, [adding, query, api]);

  const selectedIds = new Set(selected.map((b) => b.id));
  const chips = [
    ...selected,
    ...featured.filter((b) => !selectedIds.has(b.id)),
  ];

  function toggle(brand: Brand) {
    onChange(
      selectedIds.has(brand.id)
        ? selected.filter((b) => b.id !== brand.id)
        : [...selected, brand],
    );
  }

  function add(brand: Brand) {
    if (!selectedIds.has(brand.id)) onChange([...selected, brand]);
    setAdding(false);
    setQuery("");
  }

  return (
    <div>
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Brands you like"
      >
        {chips.map((brand) => {
          const on = selectedIds.has(brand.id);
          return (
            <button
              key={brand.id}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(brand)}
              className={cx(
                "inline-flex h-9 items-center gap-1.5 rounded-full border px-3.5 text-sm transition-colors",
                on
                  ? "border-btn-on bg-btn-on text-white"
                  : "border-line bg-btn-off text-ink hover:border-ink/40",
              )}
            >
              {brand.name}
              {on && <Check className="size-3.5" aria-hidden />}
            </button>
          );
        })}
        {!adding && (
          <button
            type="button"
            onClick={() => {
              setAdding(true);
              setTimeout(() => inputRef.current?.focus(), 0);
            }}
            className="inline-flex h-9 items-center gap-1 rounded-full border border-line bg-btn-off px-3.5 text-sm hover:border-ink/40"
          >
            <Plus className="size-3.5" aria-hidden /> Add brand
          </button>
        )}
      </div>

      {adding && (
        <div className="relative mt-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setAdding(false);
              if (e.key === "Enter" && results[0]) {
                e.preventDefault();
                add(results[0]);
              }
            }}
            onBlur={() => setTimeout(() => setAdding(false), 150)}
            placeholder="Search brands…"
            aria-label="Search brands"
            aria-controls={listId}
            className="h-10 w-full rounded-lg border border-line bg-frame px-3 text-sm outline-none focus:border-ink"
          />
          <ul
            id={listId}
            role="listbox"
            className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-line bg-frame py-1 shadow-lg"
          >
            {results.length === 0 && (
              <li className="px-3 py-2 text-sm text-muted">No brands found</li>
            )}
            {results.map((brand) => (
              <li
                key={brand.id}
                role="option"
                aria-selected={selectedIds.has(brand.id)}
              >
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => add(brand)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-subtle"
                >
                  {brand.name}
                  {selectedIds.has(brand.id) && (
                    <Check className="size-3.5" aria-hidden />
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
