import priceLookup from './pricing';

export function Order(quantity: number) {
  return priceLookup() * quantity;
}
