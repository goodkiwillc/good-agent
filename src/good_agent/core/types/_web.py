from typing import Literal

RequestMethod = Literal["get", "post", "put", "delete"]


# class Domain(str):
#     def __new__(cls, domain, validate: bool = True):
#         if not validate:
#             _instance = super().__new__(cls, domain)
#             return _instance
#         if not re.match(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", domain):
#             raise ValueError("Invalid domain name")

#         _instance = super().__new__(cls, domain)
#         return _instance

#     @property
#     def tld(self):
#         return self.rsplit(".", 1)[-1]

#     @property
#     def subdomains(self):
#         return tuple(self.split(".")[:-2])

#     @property
#     def root(self):
#         return self.split(".")[-2] + "." + self.tld

#     @property
#     def canonical(self):
#         # www subdomain removed by all other subdomains kept
#         subdomains = self.subdomains
#         if subdomains and subdomains[0] == "www":
#             subdomains = subdomains[1:]
#         return ".".join(list(subdomains) + [self.root])

#     @classmethod
#     def __get_pydantic_core_schema__(
#         cls, source_type: Any, handler: GetCoreSchemaHandler
#     ) -> CoreSchema:
#         return core_schema.no_info_after_validator_function(cls, handler(str))
