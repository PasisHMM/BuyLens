import { ArrowUpRight } from "lucide-react";

import { Button, ButtonLink } from "@/components/ui/primitives";
import { resolveOutboundLink, type Offer } from "@/lib/outbound";

const LABEL = "View product at retailer";

export function ViewAtRetailer({ offer }: { offer: Offer }) {
  const link = resolveOutboundLink(offer);
  return (
    <div className="flex flex-col gap-1.5 sm:items-end">
      {link ? (
        <ButtonLink href={link.href} external>
          {LABEL} <ArrowUpRight className="size-4" aria-hidden />
        </ButtonLink>
      ) : (
        <Button disabled>{LABEL}</Button>
      )}
      <p className="text-xs text-muted">
        {link
          ? `${offer.retailerName} · ${link.host}`
          : `${offer.retailerName} has no product page for this item.`}
      </p>
    </div>
  );
}
